# Scenario Analysis

在 Android 系统中，一套完整的 binder 机制包含四个部分：client、server、server-manager、binder-driver。其中 binder-driver 和 server-manager 是通信的基础，需要预创建。而 client 和 server 则依托于预创建的模块选择合适的时机进行创建。创建整体流程如下：

1. kernel 创建内核进程 swapper，该进程加载 binder-driver。
2. 系统初始化的 init 进程创建一系列的守护进程，其中就包括 server-manager。
3. server 发送注册服务消息到 server-manager。
4. client 获取 server handler。
5. client 触发消息，server 收到后处理消息。

我们不关注内核部分如何初始化化驱动，只关注用户空间内 manager 的初始化流程以及 client 和 server 的交互过程。

## server-manager 初始化

正如上面提到的，一个 server-manager 的运行流程如下：

主要只下面三个关键点：
1. 初始化化驱动。
2. 绑定当前进程到 binder 驱动。这个步骤就是告诉 binder，我是 server-manager！
3. 进入循环，等待事件。

```c
int main(int argc, char** argv)
{
    struct binder_state *bs;
    char *driver;

    if (argc > 1) {
        driver = argv[1];
    } else {
        driver = "/dev/binder";
    }

    //binder 驱动初始化
    bs = binder_open(driver, 128*1024);
  
    if (!bs) {
        ALOGE("failed to open binder driver %s\n", driver);
        return -1;
    }

    //将当前进程以 manager 的身份绑定到 binder
    if (binder_become_context_manager(bs)) {
        ALOGE("cannot become context manager (%s)\n", strerror(errno));
        return -1;
    }

    //进入 server-manager 的循环
    binder_loop(bs, svcmgr_handler);

    return 0;
}
```
### binder_open 实现

`binder_open` 其中也是三个主要操作：
1. 打开 /dev/binder 文件，这个文件对应的就是 binder 驱动。
2. 校验版本
3. 将 /dev/binder 文件前 128kb 的字段映射到用户空间。这里我就我的初步认知猜测一下这个映射的作用：binder 驱动在收到任何消息的时候，都会把消息体放置在这个 128kb的位置，此时不管是哪个进程，都可以直接读取自己用户空间的内存即可，而不需要额外进行用户空间到内核空间的交互。这里还需要注意点一个点，这个128kb也就限制了binder链路中一个消息最大是 128kb。

```c
struct binder_state
{
    int fd;
    void *mapped;
    size_t mapsize;
};

// driver: /dev/binder
// mapsize: 128 * 1024 byte
struct binder_state *binder_open(const char* driver, size_t mapsize)
{
    struct binder_state *bs; 
    struct binder_version vers; 

    bs = malloc(sizeof(*bs)); 
    if (!bs) {
        errno = ENOMEM;
        return NULL;
    }
    bs->fd = open(driver, O_RDWR | O_CLOEXEC); 
    if (bs->fd < 0) {
        fprintf(stderr,"binder: cannot open %s (%s)\n",
                driver, strerror(errno));
        goto fail_open;
    }

    //查询版本
    if ((ioctl(bs->fd, BINDER_VERSION, &vers) == -1) ||
        (vers.protocol_version != BINDER_CURRENT_PROTOCOL_VERSION)) {
        fprintf(stderr,
                "binder: kernel driver version (%d) differs from user space version (%d)\n",
                vers.protocol_version, BINDER_CURRENT_PROTOCOL_VERSION);
        goto fail_open;
    }

    //完成内存映射
    bs->mapsize = mapsize;
    bs->mapped = mmap(NULL, mapsize, PROT_READ, MAP_PRIVATE, bs->fd, 0);
    if (bs->mapped == MAP_FAILED) {
        fprintf(stderr,"binder: cannot map device (%s)\n",
                strerror(errno));
        goto fail_map;
    }

    return bs;

fail_map:
    close(bs->fd);
fail_open:
    free(bs);
    return NULL;
}
```

### binder_loop 实现

1. 通知 binder 当前进程要进入循环了。
2. 进入一个 for 循环等待消息。如果没有消息会阻塞在 ioctl BINDER_WRITE_READ 调用。
3. 收到消息后，解除阻塞，开始`binder_parse`解析数据(此时数据就在bs->mapped)，如果解析成功，会开辟新的线程异步运行 func。
4. for 循环继续。

```c
void binder_loop(struct binder_state *bs, binder_handler func)
{
    int res;
    //ioctl 读写数据类型
    struct binder_write_read bwr;
    uint32_t readbuf[32];

    bwr.write_size = 0;
    bwr.write_consumed = 0;
    bwr.write_buffer = 0;

    //告诉驱动，应用程序要进入循环了
    readbuf[0] = BC_ENTER_LOOPER;
    //ioctl 的基本封装
    binder_write(bs, readbuf, sizeof(uint32_t));

    for (;;) {
        //从驱动读数据
        bwr.read_size = sizeof(readbuf);
        bwr.read_consumed = 0;
        bwr.read_buffer = (uintptr_t) readbuf;

        res = ioctl(bs->fd, BINDER_WRITE_READ, &bwr);

        if (res < 0) {
            ALOGE("binder_loop: ioctl failed (%s)\n", strerror(errno));
            break;
        }

        //解析收到的数据，func 是解析好数据后的回调函数
        res = binder_parse(bs, 0, (uintptr_t) readbuf, bwr.read_consumed, func);
        if (res == 0) {
            ALOGE("binder_loop: unexpected reply?!\n");
            break;
        }
        if (res < 0) {
            ALOGE("binder_loop: io error %d %s\n", res, strerror(errno));
            break;
        }
    }
}
```

## binder 消息格式

binder 的消息最大为 128 kb。在初始化的时候，会将其内部分成两个连续的区块，第一个区块存储偏移量，第二个区块存储数据类型。

- 对于普通的数据，按序存储，没有提供偏移量，因此在读的时候只能按序读出。
- 对于指针类型数据，因为我们可能会有随机读取的需求，所以对于每个指针类型数据，会在偏移区存储一个偏移量。

<img src="aosp/binder/resources/binder_5.png" style="width:70%"/>


## server 发起服务注册

server 主函数流程主要包括三部分：
1. 初始化 binder。
2. 注册服务。
3. 进入循环。

```c
//注册服务 {name, callback} = {"custom-server", service_callback}
ret = svcmgr_publish(bs, svcmgr, "custom-server", service_callback);
if (ret) {
    fprintf(stderr, "failed to publish custom service\n");
    return -1;
}
```

其中 1 、3 和 server-manager 一致，这里就只对注册服务进行探究。

可以看到，一次 publish 的过程本质也是发起了一次远端调用，此时 server 是发起端，server-manager 是服务端。

```c
int svcmgr_publish(struct binder_state *bs, uint32_t target, const char *name, void *ptr)
{
    int status;
    unsigned iodata[512/4];
    struct binder_io msg, reply;

    bio_init(&msg, iodata, sizeof(iodata), 4);
    bio_put_uint32(&msg, 0);  // strict mode header
    bio_put_uint32(&msg, 0);
    bio_put_string16_x(&msg, SVC_MGR_NAME);
    bio_put_string16_x(&msg, name);
    bio_put_obj(&msg, ptr);
    bio_put_uint32(&msg, 0);
    bio_put_uint32(&msg, 0);

    if (binder_call(bs, &msg, &reply, target, SVC_MGR_ADD_SERVICE)) {
        return -1;
    }
  
    status = bio_get_uint32(&reply);
    binder_done(bs, &msg, &reply);

    return status;
}
```

## client 获取服务并请求

## server 处理服务并返回

## binder 驱动框架设计分析


<img src="aosp/binder/resources/binder_6.png" style="width:70%"/>

### 数据结构

#### binder_node

在我们一个应用层 server 被注册后，内核中就会存储一个对应的 binder_node 与之对应。每一个 binder_node 持有一个 binder_proc 对象。

```c
struct binder_node {
	//......
	struct binder_proc *proc;
	//......
}
```

#### binder_proc

binder_proc 是binder 内核对应用进程的描述.

```c
struct binder_proc {
	//......
	struct binder_context *context;
	//......
}
```

#### binder_ref

内核中对 binder_node 的引用，可以通过 binder_ref 找到对应的 binder_node。


### 寻址

#### 如何找到 server-manager

如何找到 server-manager? client 、server 都会处于需要去查找 server-manager。

1. 在每个 binder 进程初始化时。都会将 binder_device 的 context 成员绑定在自己 binder_proc 的 context 成员上。binder_device 是全局唯一的，所以所有的 binder_proc 对象都会访问同一个 context 对象。

2. 在 server-manager 注册自己的时候(`binder_become_context_manager`). binder 驱动会把 server-manager 对应的 binder_node 绑定在 context 的 binder_context_mgr_node 上。

3. 所以所有的 binder_node, 都会通过自己的 binder_proc 成员拿到 context，并从context 中拿到 server-manager。

#### 如何找到 server

##### server 注册阶段

<img src="aosp/binder/resources/binder_7.png"/>

1. server 向 server-manager 发起服务注册请求的时候，首先创建对应的 binder_node 对象，随后这个 binder_node 对象被保存在 server 对应的 binder_proc->nodes 中，这个 nodes 是一个红黑树。

2. 随后创建一个该 binder_node 的引用 binder_ref, 将其存储在 server-manager 对应的 binder_proc 下的 refs_by_desc 红黑树中。最终 server-manager 的这可红黑树会被映射到应用层的一个链表中。



##### server 获取阶段

1. client 向 server-manager 获取对应的服务 handler。

- client 发起服务请求的时候，首先从自己的 binder_proc 中找到 context，进而找到对应的 server-manager 对应的 binder_proc。

- binder 将 client 对应的请求体复制到内核中，server-manager 发现有数据，从 binder_loop 中激活，通过 mmap 获取到请求体，并调用回调函数。

- 回调函数总查找对应的链表，找到对应的服务的 handler，同时会在内核中找到对应的红黑树上的binder_ref,并将其也绑定在 client->refs_by_desc 上，这也是个红黑树。最终构造好 client 内核中的数据后，返回 handle 到 client 的应用层。

2. client 向 server 发起调用。

- client 通过 handler 发起远端调用，会陷入内核，此时会从 client 自身的 refs_by_desc 通过 handler 获取到对应的 binder_ref, 进而 binder_ref->binder_node->binder_proc 就可以获取到对应的服务进程。

- 随后 binder 驱动会把请求数据复制到内核空间，对应服务进程会从 binder_loop 中激活，进而处理该消息。


## Binder 驱动情景分析

### server-manager 启动过程



### 服务注册过程

### 服务获取与调用过程


