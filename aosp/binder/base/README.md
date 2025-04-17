# What is binder?

## 总览

binder 是 Android 系统中的一套 进程间通信（IPC） 框架，其命名源于底层依赖 Linux 内核的 binder 驱动。
binder 驱动的核心功能包括：

- 服务注册与发现：允许一个 Service Manager（早期版本中的核心组件）统一管理多个 Server 服务。

- 跨进程调用：Client 可通过 binder 驱动查询到目标 Server 的引用（以 binder Proxy 形式返回），并通过该引用发起远程方法调用（RPC）。

- 高效数据传输：binder 利用内存映射（mmap）机制在进程间共享数据，仅需一次拷贝（从发送方用户空间到内核空间，接收方直接访问映射的内核缓冲区），相比传统 IPC（如管道/Socket）减少数据拷贝次数，从而提升性能。

<img src="aosp/binder/resources/binder_2.png" style="width:50%"/>

<img src="aosp/binder/resources/binder_1.png" style="width:70%"/>

从架构图中可以看到 binder 横跨了应用层到内核层，是维持整个系统通信链路的基石。

- 内核层： binder 底层驱动由内核管理，并暴露出方便使用 binder 的 libbinder 库。
- native层：在 server manager 由 native 层实现。同时也实现了一些 native 版本的 client 和 server。
- jni层：通过对 libbinder 封装，暴露给 java 层使用。
- java层：借助于 jni 的接口，可以对 native server进行调用，也可以实现 java 版本的 client 和 server。

整个 binder 本身是一个 cs 架构，其中 server-manager 管理所有的 server，提供服务发现的能力。

1. client 通过 server-manager 拿到对用的服务 handler。
2. 直接调用这个 handler 触发 server 执行。

<img src="aosp/binder/resources/binder_3.png" style="width:70%"/>


---
<img src="aosp/binder/resources/binder_4.png" style="width:100%"/>

## Server 实现


### 开发服务

所谓的服务就是函数，对于一个 server 进程，可能提供多种服务。

```c
void action1(void){
    printf("HelloWorld\n");
}


int action2(char * msg){
    return strlen(msg);
}
```

### 开发服务回调函数

一个 server 进程会向 server-manager 绑定一个回调函数的指针，当 client 查找服务的时候，server-manager 会返回这个回调地址，后续调用的时候，也是直接触发的这个回调函数，而不是具体的 action. 具体是哪个 action，则要看 client 传进来的标识。回调中通过标识来路由到不同的 action。

```c
int service_callback(struct binder_state *bs,
                   struct binder_transaction_data_secctx *txn_secctx,
                   struct binder_io *msg,
                   struct binder_io *reply) {
    struct binder_transaction_data *txn = &txn_secctx->transaction_data;
    switch(txn->code) {
        case CUSTOM_SERVER_ACTION1:
            action1();
            bio_put_uint32(reply, 0);
            return 0;
        case CUSTOM_SERVER_ACTION2:
            uint16_t *s;
            char name[512];
            size_t len;
            s = bio_get_string16(msg, &len);  // name
            if (s == NULL) {
	            return -1;
            }
            for (i = 0; i < len; i++)
                name[i] = s[i];
            name[i] = '\0';
            i = action2(name);
            bio_put_uint32(reply, 0); /* no exception */
            bio_put_uint32(reply, i);
            break;

        default:
            fprintf(stderr, "unknown code %d\n", txn->code);
            return -1;
    }             
}
```

### 开发 Loop 回调函数

每一个 server 都会持有一个消息请求队列，server 在运行的时候会监听这个队列，在队列中有任务的时候，就会取出来任务，进行执行。这个流程实现在 Loop 回调函数中。

```c
int loop_callback(struct binder_state *bs,
                struct binder_transaction_data_secctx *txn_secctx,
                struct binder_io *msg,
                struct binder_io *reply)
{
    struct binder_transaction_data *txn = &txn_secctx->transaction_data;
	
    int (*handler)(struct binder_state *bs,
                   struct binder_transaction_data *txn,
                   struct binder_io *msg,
                   struct binder_io *reply);

	handler = (int (*)(struct binder_state *bs,
                   struct binder_transaction_data *txn,
                   struct binder_io *msg,
                   struct binder_io *reply))txn->target.ptr;
	
	return handler(bs, txn, msg, reply);
}
```

### 初始化 Binder, 注册服务, 启动 Loop

```c
int main(int argc, char **argv)
{
    struct binder_state *bs;
    uint32_t svcmgr = BINDER_SERVICE_MANAGER;
    uint32_t handle;
	int ret;
  
    //Binder 初始化
    bs = binder_open("/dev/binder", 128*1024);
    if (!bs) {
        fprintf(stderr, "failed to open binder driver\n");
        return -1;
    }

	//注册服务 {name, callback} = {"custom-server", service_callback}
	ret = svcmgr_publish(bs, svcmgr, "custom-server", service_callback);
    if (ret) {
        fprintf(stderr, "failed to publish custom service\n");
        return -1;
    }
    //进入 loop， 等待 client 请求服务
    // 这里实际上是在等待一个队列中出现任务。
    // 这个队列是 mmap 从用户空间映射到内核空间，由 binder drive 管理。
    // client 发送请求会被 binder 拋送到这个 server 进程的队列中。
    binder_loop(bs, loop_callback);
    return 0;
}
```

## Server-Manager 实现

server-manager 用来持有所有的服务名到 server_callback 的指针。

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

## Client 实现

### 定义服务调用函数

```c
void requestAction1(void)
{
    unsigned iodata[512/4];
    //binder_io 可以理解为一个数据集合，用于存取数据
    struct binder_io msg, reply;

	/* 构造binder_io */
    bio_init(&msg, iodata, sizeof(iodata), 4);

	/* 放入参数 */

	/* 调用 binder_call 发起远程调用 */
    if (binder_call(g_bs, &msg, &reply, g_handle, CUSTOM_SERVER_ACTION1))
        return ;

	/* 从reply中解析出返回值 */

    binder_done(g_bs, &msg, &reply);

}

int requestAction2(char *name)
{
	unsigned iodata[512/4];
	struct binder_io msg, reply;
	int ret;
	int exception;

	/* 构造binder_io */
	bio_init(&msg, iodata, sizeof(iodata), 4);

	/* 放入参数 */
    bio_put_string16_x(&msg, name);

	/* 调用binder_call  发起远程调用*/
	if (binder_call(g_bs, &msg, &reply, g_handle, CUSTOM_SERVER_ACTION2))
		return 0;

	/* 从reply中解析出返回值 */
	exception = bio_get_uint32(&reply);
	if (exception)
		ret = -1;
	else
		ret = bio_get_uint32(&reply);

	binder_done(g_bs, &msg, &reply);

	return ret;
}
```

### 初始化，服务触发

```c
int g_handle = 0;
struct binder_state *g_bs;

int main(int argc, char **argv)
{
    int fd;
    struct binder_state *bs;
    uint32_t svcmgr = BINDER_SERVICE_MANAGER;
	int ret;

    //初始化 binder 驱动
    bs = binder_open("/dev/binder", 128*1024);
    if (!bs) {
        fprintf(stderr, "failed to open binder driver\n");
        return -1;
    }

    g_bs = bs;

	//查找服务，获取到服务的句柄 handle，用于找到 Server 进程
    g_handle = svcmgr_lookup(bs, svcmgr, "custom-server");
    if (!g_handle) {
        ALOGW("binder client 查找服务 custom-server 失败");
        return -1;
    } else {
        ALOGW("binder client 查找服务成功 handle = %d", g_handle);
    }

    //通过 handle 调用服务
    requestAction1();
    requestAction2("hello binder");

    return 0;
}
```

