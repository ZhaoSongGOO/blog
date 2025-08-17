# Service Manager 启动过程

Service Manager 是Binder 进程间通信机制的核心组件之一，它扮演着 Binder 进程间通信机制上下文管理者(Context Manager)的角色，同时负责管理系统中的 Service 组件，并且向 Client 组件提供获取 Service 代理对象的服务。

Service Manager 运行在一个独立的进程中，因此，Service 组件和 Client 组件也需要通过进程间通信机制来和它交互，而采用的进程间通信机制正好也是 Binder 进程间通信机制。从这个角度来看，Service Manager 除了是 Binder 进程间通信机制的上下文管理者(Context Manager)之外，它也是一个特殊的 Service 组件。

Service Manager 是由 init 进程负责启动的，而 init 进程是在系统启动时启动的，因此，Service Manager 也是在系统启动时启动的，对应的二进制文件是 /system/bin/servicemanager。

其源码位于 frameworks/base/cmds/servicemanager 目录下。

其启动逻辑如下，

```c
int main(int argc, char **argv)
{
    struct binder_state *bs;
    void *svcmgr = BINDER_SERVICE_MANAGER;

    bs = binder_open(128*1024); // 打开设备文件并映射缓冲区

    // 将自己注册为 binder 上下文管理者
    if (binder_become_context_manager(bs)) {
        LOGE("cannot become context manager (%s)\n", strerror(errno));
        return -1;
    }

    svcmgr_handle = svcmgr;
    // 循环等待和处理 client 进程通信请求。
    binder_loop(bs, svcmgr_handler);
    return 0;
}
```

其中 binder_state 的内容如下

```c
struct binder_state
{
    int fd; // /dev/binder 的文件描述符
    void *mapped;  // 映射的内核缓冲区空间地址
    unsigned mapsize; // 映射的内核缓冲区空间大小
};
```

前面提到，Service Manager 是一个特殊的 Service 组件，它的特殊之处就在于与它对应的 Binder 本地对象是一个虚拟的对象。这个虚拟的 Binder 本地对象的地址值等于 0，并且在 Binder 驱动程序中引用了它的 Binder 引用对象的句柄值也等于 0。

```c
#define BINDER_SERVICE_MANAGER ((void*) 0)
```

## 打开设备文件并映射缓冲区

```c
struct binder_state *binder_open(unsigned mapsize)
{
    struct binder_state *bs;

    bs = malloc(sizeof(*bs));
    if (!bs) {
        errno = ENOMEM;
        return 0;
    }
    // 用函数open打开设备文件/dev/binder。
    // 当使用进程函数open打开设备文件/dev/binder时，Binder驱动程序中的函数binder_open就会被调用，
    // 它会为当前进程创建一个binder_proc结构体，用来描述当前进程的Binder进程间通信状态。
    bs->fd = open("/dev/binder", O_RDWR);
    if (bs->fd < 0) {
        fprintf(stderr,"binder: cannot open device (%s)\n",
                strerror(errno));
        goto fail_open;
    }

    bs->mapsize = mapsize;
    // 调用函数mmap将设备文件/dev/binder映射到进程的地址空间，它请求映射的地址空间大小为mapsize，
    // 即请求Binder驱动程序为进程分配128K大小的内核缓冲区。
    bs->mapped = mmap(NULL, mapsize, PROT_READ, MAP_PRIVATE, bs->fd, 0);
    if (bs->mapped == MAP_FAILED) {
        fprintf(stderr,"binder: cannot map device (%s)\n",
                strerror(errno));
        goto fail_map;
    }

        /* TODO: check version */

    return bs;

fail_map:
    close(bs->fd);
fail_open:
    free(bs);
    return 0;
}
```

## 注册为上下文管理者

这个逻辑就很简单了，直接使用 ioctl 发送一个控制命令给 binder 驱动。

```c
int binder_become_context_manager(struct binder_state *bs)
{
    return ioctl(bs->fd, BINDER_SET_CONTEXT_MGR, 0);
}
```

这个方法会触发 binder 驱动的 binder_ioctl 回调，在回调中，逻辑如下，

```c
static long binder_ioctl(struct file *filp, unsigned int cmd, unsigned long arg) {
    //...
    // 生成 当前线程的 binder_thread 结构体
    // 如果是新创建，会设置状态为 BINDER_LOOPER_STATE_NEED_RETURN，
    // 表示该线程在完成当前操作之后，需要马上返回到用户空间，而不可以去处理进程间的通信请求。
    thread = binder_get_thread(proc);
    //...
	case BINDER_SET_CONTEXT_MGR:
        // 不允许重复注册
		if (binder_context_mgr_node != NULL) {
			printk(KERN_ERR "binder: BINDER_SET_CONTEXT_MGR already set\n");
			ret = -EBUSY;
			goto err;
		}
        // 因为一个进程上一次可能注册失败，所以允许同一个进程重复注册
		if (binder_context_mgr_uid != -1) {
			if (binder_context_mgr_uid != current->cred->euid) {
				printk(KERN_ERR "binder: BINDER_SET_"
				       "CONTEXT_MGR bad uid %d != %d\n",
				       current->cred->euid,
				       binder_context_mgr_uid);
				ret = -EPERM;
				goto err;
			}
		} else
			binder_context_mgr_uid = current->cred->euid;
        // 创建对应的 binder_node 对象，创建的时候，会把这个 bidner_node 顺手挂在 binder_proc 的红黑树上。
		binder_context_mgr_node = binder_new_node(proc, NULL, NULL);
		if (binder_context_mgr_node == NULL) {
			ret = -ENOMEM;
			goto err;
		}
		binder_context_mgr_node->local_weak_refs++;
		binder_context_mgr_node->local_strong_refs++;
		binder_context_mgr_node->has_strong_ref = 1;
		binder_context_mgr_node->has_weak_ref = 1;
		break;
    //...

    if (thread)
		thread->looper &= ~BINDER_LOOPER_STATE_NEED_RETURN; // 清空标志位，使得下一次该线程可以接收通信请求。
}
```

## 循环等待 Client 进程请求


```c
int binder_write(struct binder_state *bs, void *data, unsigned len)
{
    struct binder_write_read bwr;
    int res;
    bwr.write_size = len;
    bwr.write_consumed = 0;
    bwr.write_buffer = (unsigned) data;
    bwr.read_size = 0;
    bwr.read_consumed = 0;
    bwr.read_buffer = 0;
    res = ioctl(bs->fd, BINDER_WRITE_READ, &bwr);
    if (res < 0) {
        fprintf(stderr,"binder_write: ioctl failed (%s)\n",
                strerror(errno));
    }
    return res;
}

// func 回调函数
void binder_loop(struct binder_state *bs, binder_handler func)
{
    int res;
    struct binder_write_read bwr;
    unsigned readbuf[32];

    bwr.write_size = 0;
    bwr.write_consumed = 0;
    bwr.write_buffer = 0;
    
    readbuf[0] = BC_ENTER_LOOPER;
    // 设置当前线程的状态为 BINDER_LOOPER_STATE_ENTERED，代表其可以处理进程间通信请求
    binder_write(bs, readbuf, sizeof(unsigned));

    for (;;) {
        bwr.read_size = sizeof(readbuf);
        bwr.read_consumed = 0;
        bwr.read_buffer = (unsigned) readbuf;
        // 循环不断使用IO控制命令BINDER_WRITE_READ来检查Binder驱动程序是否有新的进程间通信请求需要它来处理。
        // 如果有，就将它们交给函数binder_parse来处理；否则，当前线程就会在Binder驱动程序中睡眠等待，直到有新的进程间通信请求到来为止。
        res = ioctl(bs->fd, BINDER_WRITE_READ, &bwr);

        if (res < 0) {
            LOGE("binder_loop: ioctl failed (%s)\n", strerror(errno));
            break;
        }

        res = binder_parse(bs, 0, readbuf, bwr.read_consumed, func);
        if (res == 0) {
            LOGE("binder_loop: unexpected reply?!\n");
            break;
        }
        if (res < 0) {
            LOGE("binder_loop: io error %d %s\n", res, strerror(errno));
            break;
        }
    }
}
```

## Service Manager 代理对象的获取过程

Service Manager 代理对象的类型为 BpServiceManager，它用来描述一个实现了 IServiceManager 接口的 Client 组件。

<img src="android/framework/binder/service_manager/resources/1.png" style="width:100%">

在 c++ 中获取 Service Manager 的方法如下.

```cpp
sp<IServiceManager> defaultServiceManager()
{
    if (gDefaultServiceManager != NULL) return gDefaultServiceManager;
    
    {
        AutoMutex _l(gDefaultServiceManagerLock);
        if (gDefaultServiceManager == NULL) {
            gDefaultServiceManager = interface_cast<IServiceManager>(
                ProcessState::self()->getContextObject(NULL));
        }
    }
    
    return gDefaultServiceManager;
}

sp<IBinder> ProcessState::getContextObject(const sp<IBinder>& caller)
{
    if (supportsProcesses()) {
        // 只有打开了 /dev/binder 的进程才支持 binder 通信，
        return getStrongProxyForHandle(0);
    } else {
        return getContextObject(String16("default"), caller);
    }
}

sp<IBinder> ProcessState::getStrongProxyForHandle(int32_t handle)
{
    sp<IBinder> result;

    AutoMutex _l(mLock);

    handle_entry* e = lookupHandleLocked(handle); // 这个里面不存在就会创建，所以要是没有错误的话，一般返回都不是 null

    if (e != NULL) {
        // We need to create a new BpBinder if there isn't currently one, OR we
        // are unable to acquire a weak reference on this current one.  See comment
        // in getWeakProxyForHandle() for more info about this.
        IBinder* b = e->binder;
        if (b == NULL || !e->refs->attemptIncWeak(this)) {
            b = new BpBinder(handle); 
            e->binder = b;
            if (b) e->refs = b->getWeakRefs();
            result = b;
        } else {
            // This little bit of nastyness is to allow us to add a primary
            // reference to the remote proxy when this team doesn't have one
            // but another team is sending the handle to us.
            result.force_set(b);
            e->refs->decWeak(this);
        }
    }

    return result;
}
```

## Server 组件启动过程

Service 组件是在 Server 进程中运行的。Server 进程在启动时，会首先将它里面的 Service 组件注册到 Service Manager 中，接着再启动一个 Binder 线程池来等待和处理 Client 进程的通信请求

在使用 defaultServiceManager 拿到 BpServiceManager 之后，会使用其 addService 方法来注册服务。

```cpp
virtual status_t addService(const String16& name, const sp<IBinder>& service)
{
    Parcel data, reply;
    data.writeInterfaceToken(IServiceManager::getInterfaceDescriptor());
    data.writeString16(name);
    data.writeStrongBinder(service);
    // 调用远程的 BpBinder 对象发送数据
    status_t err = remote()->transact(ADD_SERVICE_TRANSACTION, data, &reply);
    return err == NO_ERROR ? reply.readExceptionCode() : err;
}
```

### 封装进程间通信数据

1. 写入 binder 通信头数据

Binder 进程间通信请求头由两部分内容组成。第一部分内容是一个整数值，用来描述一个 Strict Mode Policy, 第二部分内容是一个字符串，用来描述所请求服务的接口描述符。

```cpp
// data.writeInterfaceToken(IServiceManager::getInterfaceDescriptor());
status_t Parcel::writeInterfaceToken(const String16& interface)
{
    writeInt32(IPCThreadState::self()->getStrictModePolicy() |
               STRICT_MODE_PENALTY_GATHER);
    // currently the interface identification token is just its name as a string
    return writeString16(interface);
}
```

2. 写入 Server 组件名称

`data.writeString16(name)`


3. 将需要注册的 Server 组件封装成 flat_binder_object 结构体。

```cpp
// data.writeStrongBinder(service);
status_t Parcel::writeStrongBinder(const sp<IBinder>& val)
{
    return flatten_binder(ProcessState::self(), val, this);
}

status_t flatten_binder(const sp<ProcessState>& proc,
    const sp<IBinder>& binder, Parcel* out)
{   
    // 传入的 binder 是个 BBinder 对象。
    flat_binder_object obj;
    
    obj.flags = 0x7f | FLAT_BINDER_FLAG_ACCEPTS_FDS;
    if (binder != NULL) {
        // 因为是 BBinder，所以这里不为 null
        /*
            BBinder* BBinder::localBinder()
            {
                return this;
            }
        */
        IBinder *local = binder->localBinder();
        if (!local) {
            BpBinder *proxy = binder->remoteBinder();
            if (proxy == NULL) {
                LOGE("null proxy");
            }
            const int32_t handle = proxy ? proxy->handle() : 0;
            obj.type = BINDER_TYPE_HANDLE;
            obj.handle = handle;
            obj.cookie = NULL;
        } else {
            obj.type = BINDER_TYPE_BINDER;
            obj.binder = local->getWeakRefs();
            obj.cookie = local;
        }
    } else {
        obj.type = BINDER_TYPE_BINDER;
        obj.binder = NULL;
        obj.cookie = NULL;
    }
    // 将该对象写入 Parcel 结构中
    return finish_flatten_binder(binder, obj, out);
}
```

### 发送和处理 BC_TRANSACTION 命令协议

发起远程调用的数据转换大概是这样，

- 用户数据到 -> Parcel 数据。
- 因为远程调用的协议 BINDER_TRANSACTION 后面要求 binder_transaction_data 数据，所以Parcel 数据 写入 binder_transaction_data。 
- 这些数据需要使用 BINDER_WRITE_READ 控制符通知驱动，所以 binder_transcation_data 需要写入到 binder_write_read 结构中。

明确这点后，我们研究远程调用发起的过程。

writeTransactionData 会把这些数据写入到 mOut 中，此时 mOut 的内容如下.

<img src="android/framework/binder/service_manager/resources/2.png" style="width:50%">



```cpp
// status_t err = remote()->transact(ADD_SERVICE_TRANSACTION, data, &reply);
status_t BpBinder::transact(
    uint32_t code, const Parcel& data, Parcel* reply, uint32_t flags)
{
    // Once a binder has died, it will never come back to life.
    if (mAlive) {
        status_t status = IPCThreadState::self()->transact(
            mHandle, code, data, reply, flags);
        if (status == DEAD_OBJECT) mAlive = 0;
        return status;
    }

    return DEAD_OBJECT;
}

status_t IPCThreadState::transact(int32_t handle,
                                  uint32_t code, const Parcel& data,
                                  Parcel* reply, uint32_t flags)
{
    status_t err = data.errorCheck();

    flags |= TF_ACCEPT_FDS;

    IF_LOG_TRANSACTIONS() {
        TextOutput::Bundle _b(alog);
        alog << "BC_TRANSACTION thr " << (void*)pthread_self() << " / hand "
            << handle << " / code " << TypeCode(code) << ": "
            << indent << data << dedent << endl;
    }
    
    if (err == NO_ERROR) {
        LOG_ONEWAY(">>>> SEND from pid %d uid %d %s", getpid(), getuid(),
            (flags & TF_ONE_WAY) == 0 ? "READ REPLY" : "ONE WAY");
        // 将 Parcel 数据写入到 binder_transaction_data 结构体
        // 进一步缓存到 binder_write_read 结构体
        // 就是之前一直出现的 mOut 的什么玩意。
        err = writeTransactionData(BC_TRANSACTION, flags, handle, code, data, NULL);
    }
    
    if (err != NO_ERROR) {
        if (reply) reply->setError(err);
        return (mLastError = err);
    }
    
    if ((flags & TF_ONE_WAY) == 0) {
        if (reply) {
            err = waitForResponse(reply);
        } else {
            Parcel fakeReply;
            err = waitForResponse(&fakeReply);
        }
        
        IF_LOG_TRANSACTIONS() {
            TextOutput::Bundle _b(alog);
            alog << "BR_REPLY thr " << (void*)pthread_self() << " / hand "
                << handle << ": ";
            if (reply) alog << indent << *reply << dedent << endl;
            else alog << "(none requested)" << endl;
        }
    } else {
        err = waitForResponse(NULL, NULL);
    }
    
    return err;
}
```

随后调用 waitForResponse 向 binder 驱动发起请求。这个函数通过一个 while 循环不断地调用成员函数 talkWithDriver 来与 Binder 驱动程序进行交互，以便可以将前面准备好的 BC_TRANSACTION 命令协议发送给 Binder 驱动程序处理，并等待 Binder 驱动程序将进程间通信结果返回来。

在 IPCThreadState 类内部，除了使用缓冲区 mOut 来保存即将要发送给 Binder 驱动程序的命令协议之外，还使用缓冲区 mIn 来保存那些从 Binder 驱动程序接收到的返回协议。从前面的调用过程可以知道，缓冲区 mOut 里面存在一个 BC_TRANSACTION 命令协议。

```cpp
status_t IPCThreadState::waitForResponse(Parcel *reply, status_t *acquireResult)
{
    int32_t cmd;
    int32_t err;

    while (1) {
        if ((err=talkWithDriver()) < NO_ERROR) break;
        //...
    }
    
    return err;
}

status_t IPCThreadState::talkWithDriver(bool doReceive)
{    
    binder_write_read bwr;
    
    // Is the read buffer empty?
    const bool needRead = mIn.dataPosition() >= mIn.dataSize();
    
    // We don't want to write anything if we are still reading
    // from data left in the input buffer and the caller
    // has requested to read the next data.
    const size_t outAvail = (!doReceive || needRead) ? mOut.dataSize() : 0;
    
    bwr.write_size = outAvail;
    bwr.write_buffer = (long unsigned int)mOut.data();

    // This is what we'll read.
    if (doReceive && needRead) {
        bwr.read_size = mIn.dataCapacity();
        bwr.read_buffer = (long unsigned int)mIn.data();
    } else {
        bwr.read_size = 0;
    }
    //...
    
    // Return immediately if there is nothing to do.
    if ((bwr.write_size == 0) && (bwr.read_size == 0)) return NO_ERROR;
    
    bwr.write_consumed = 0;
    bwr.read_consumed = 0;
    status_t err;
    do {
        if (ioctl(mProcess->mDriverFD, BINDER_WRITE_READ, &bwr) >= 0)
            err = NO_ERROR;
        else
            err = -errno;
    } while (err == -EINTR);
    

    if (err >= NO_ERROR) {
        if (bwr.write_consumed > 0) {
            if (bwr.write_consumed < (ssize_t)mOut.dataSize())
                mOut.remove(0, bwr.write_consumed);
            else // 发完之后，就清除发送的数据
                mOut.setDataSize(0);
        }
        if (bwr.read_consumed > 0) {
            mIn.setDataSize(bwr.read_consumed);
            mIn.setDataPosition(0);
        }
        return NO_ERROR;
    }
    
    return err;
}
```

随后 ioctl 后进入到我们熟悉的 binder 驱动代码，binder 驱动首先处理本次通信发送过来的消息，调用 binder_thread_write 方法。

```c
		case BC_TRANSACTION:
		case BC_REPLY: {
			struct binder_transaction_data tr;
            // 从用户空间拷贝出来 binder_transaction_data 数据
			if (copy_from_user(&tr, ptr, sizeof(tr)))
				return -EFAULT;
			ptr += sizeof(tr);
            // 调用 binder_transaction 方法
			binder_transaction(proc, thread, &tr, cmd == BC_REPLY);
			break;
		}
```

在 binder_transaction 中，首先会判断 handler 是不是 0, 如果是 0 直接使用 binder_context_mgr_node，不是 0的话，将首先获取对应的 binder_ref, 然后再从 binder_ref 获取到 binder_node。

```c
		if (tr->target.handle) {
			struct binder_ref *ref;
			ref = binder_get_ref(proc, tr->target.handle);
			if (ref == NULL) {
				binder_user_error("binder: %d:%d got "
					"transaction to invalid handle\n",
					proc->pid, thread->pid);
				return_error = BR_FAILED_REPLY;
				goto err_invalid_target_handle;
			}
			target_node = ref->node;
		} else {
			target_node = binder_context_mgr_node;
			if (target_node == NULL) {
				return_error = BR_DEAD_REPLY;
				goto err_no_context_mgr_node;
			}
		}
		e->to_node = target_node->debug_id;
		target_proc = target_node->proc;
		if (target_proc == NULL) {
			return_error = BR_DEAD_REPLY;
			goto err_dead_binder;
		}
        // 一个优化，为了提高目标进程的并发效率，计算最佳的目标线程
		if (!(tr->flags & TF_ONE_WAY) && thread->transaction_stack) {
			struct binder_transaction *tmp;
			tmp = thread->transaction_stack;
			if (tmp->to_thread != thread) {
				binder_user_error("binder: %d:%d got new "
					"transaction with bad transaction stack"
					", transaction %d has target %d:%d\n",
					proc->pid, thread->pid, tmp->debug_id,
					tmp->to_proc ? tmp->to_proc->pid : 0,
					tmp->to_thread ?
					tmp->to_thread->pid : 0);
				return_error = BR_FAILED_REPLY;
				goto err_bad_call_stack;
			}
			while (tmp) {
				if (tmp->from && tmp->from->proc == target_proc)
					target_thread = tmp->from;
				tmp = tmp->from_parent;
			}
		}
        if (target_thread) {
            e->to_thread = target_thread->pid;
            target_list = &target_thread->todo;
            target_wait = &target_thread->wait;
        } else {
            target_list = &target_proc->todo;
            target_wait = &target_proc->wait;
        }
```

得到目标 TODO 队列后，构造 binder_transaction 对象，拷贝数据到内核缓冲区。

```c
	/* TODO: reuse incoming transaction for reply */
    // 构造一个 binder_transaction 结构体，用于后续假如到目标队列中
	t = kzalloc(sizeof(*t), GFP_KERNEL);
    //...

    // 构造一个 binder_work, 这个类型是 BINDER_WORK_TRANSACTION_COMPLETE，用于发给源线程。
    // 让其知道自己发起的请求已经被接收
	tcomplete = kzalloc(sizeof(*tcomplete), GFP_KERNEL);
	//...
    // 记录源线程，使得后续处理结果可以找到返回的目标
	if (!reply && !(tr->flags & TF_ONE_WAY))
		t->from = thread;
	else
		t->from = NULL;
	t->sender_euid = proc->tsk->cred->euid;
	t->to_proc = target_proc;
	t->to_thread = target_thread;
	t->code = tr->code;
	t->flags = tr->flags;
	t->priority = task_nice(current);
    // 分配内核缓冲区，后续用来存放进程间通信数据
	t->buffer = binder_alloc_buf(target_proc, tr->data_size,
		tr->offsets_size, !reply && (t->flags & TF_ONE_WAY));
	if (t->buffer == NULL) {
		return_error = BR_FAILED_REPLY;
		goto err_binder_alloc_buf_failed;
	}
	t->buffer->allow_user_free = 0;
	t->buffer->debug_id = t->debug_id;
	t->buffer->transaction = t;
	t->buffer->target_node = target_node;
	if (target_node) // 增加强引用计数
		binder_inc_node(target_node, 1, 0, NULL);

	offp = (size_t *)(t->buffer->data + ALIGN(tr->data_size, sizeof(void *)));

	if (copy_from_user(t->buffer->data, tr->data.ptr.buffer, tr->data_size)) {
		binder_user_error("binder: %d:%d got transaction with invalid "
			"data ptr\n", proc->pid, thread->pid);
		return_error = BR_FAILED_REPLY;
		goto err_copy_data_failed;
	}
	if (copy_from_user(offp, tr->data.ptr.offsets, tr->offsets_size)) {
		binder_user_error("binder: %d:%d got transaction with invalid "
			"offsets ptr\n", proc->pid, thread->pid);
		return_error = BR_FAILED_REPLY;
		goto err_copy_data_failed;
	}
    //...
	off_end = (void *)offp + tr->offsets_size;
```

现在有数据了，继续执行。for循环依次处理进程间通信数据中的Binder对象。如果Binder驱动程序是第一次碰到这些 Binder对象，那么Binder驱动程序就会根据它们的类型分别创建一个Binder实体对象或者一个Binder引用对象；否则，就会将之前为它们创建的Binder实体对象或者Binder引用对象获取回来，以便可以增加它们的引用计数，避免它们过早地被销毁。

从前面的调用过程可以知道，进程间通信数据中包含有一个类型为BINDER_TYPE_BINDER的Binder对象，即一个flat_binder_object结构体。由于Binder驱动程序是第一次碰到这个Binder对象，因此调用函数binder_get_node就无法获得一个引用了它的Binder实体对象，接着第99行就会调用函数binder_new_node为它创建一个Binder实体对象node。

Service组件从源进程proc传递到目标进程target_proc中，因此需要调用函数 binder_get_ref_for_node 在目标进程 target_proc 中创建一个 Binder 引用对象来引用该 Service 组件。

```c

	for (; offp < off_end; offp++) {
		struct flat_binder_object *fp;
		if (*offp > t->buffer->data_size - sizeof(*fp) ||
		    t->buffer->data_size < sizeof(*fp) ||
		    !IS_ALIGNED(*offp, sizeof(void *))) {
			binder_user_error("binder: %d:%d got transaction with "
				"invalid offset, %zd\n",
				proc->pid, thread->pid, *offp);
			return_error = BR_FAILED_REPLY;
			goto err_bad_offset;
		}
		fp = (struct flat_binder_object *)(t->buffer->data + *offp);
		switch (fp->type) {
		case BINDER_TYPE_BINDER:
		case BINDER_TYPE_WEAK_BINDER: {
			struct binder_ref *ref;
			struct binder_node *node = binder_get_node(proc, fp->binder);
			if (node == NULL) {
                // 发现 这个 binder 本地对象还没有对应的 binder 实体对象，就创建一个新的
				node = binder_new_node(proc, fp->binder, fp->cookie);
				if (node == NULL) {
					return_error = BR_FAILED_REPLY;
					goto err_binder_new_node_failed;
				}
				node->min_priority = fp->flags & FLAT_BINDER_FLAG_PRIORITY_MASK;
				node->accept_fds = !!(fp->flags & FLAT_BINDER_FLAG_ACCEPTS_FDS);
			}
			if (fp->cookie != node->cookie) {
				binder_user_error("binder: %d:%d sending u%p "
					"node %d, cookie mismatch %p != %p\n",
					proc->pid, thread->pid,
					fp->binder, node->debug_id,
					fp->cookie, node->cookie);
				goto err_binder_get_ref_for_node_failed;
			}
            // 在目标进程中给服务组件的实体对象创建一个引用 binder_ref。
			ref = binder_get_ref_for_node(target_proc, node);
			if (ref == NULL) {
				return_error = BR_FAILED_REPLY;
				goto err_binder_get_ref_for_node_failed;
			}
			if (fp->type == BINDER_TYPE_BINDER)
				fp->type = BINDER_TYPE_HANDLE;
			else
				fp->type = BINDER_TYPE_WEAK_HANDLE;
			fp->handle = ref->desc;
			binder_inc_ref(ref, fp->type == BINDER_TYPE_HANDLE, &thread->todo);
			//...
		} break;
        //...
    
        }
    }
```

随后给目标 todo 队列中增加任务，并唤醒目标。

```c
	if (reply) {
		//...
	} else if (!(t->flags & TF_ONE_WAY)) {
		BUG_ON(t->buffer->async_transaction != 0);
		t->need_reply = 1;
		t->from_parent = thread->transaction_stack;
		thread->transaction_stack = t;
	} else {
		BUG_ON(target_node == NULL);
		BUG_ON(t->buffer->async_transaction != 1);
		if (target_node->has_async_transaction) {
			target_list = &target_node->async_todo;
			target_wait = NULL;
		} else
			target_node->has_async_transaction = 1;
	}
    // 封装工作类型，并添加到目标任务队列中。
	t->work.type = BINDER_WORK_TRANSACTION;
	list_add_tail(&t->work.entry, target_list);
	tcomplete->type = BINDER_WORK_TRANSACTION_COMPLETE;
    // 给源线程发送回复消息。
	list_add_tail(&tcomplete->entry, &thread->todo);
    // 唤醒目标队列
	if (target_wait)
		wake_up_interruptible(target_wait);
	return;
```

对于源线程，等 binder_transaction 这个函数执行完成后，返回到 binder_ioctl 函数，此时因为队列中有一个 回复的消息 BINDER_WORK_TRANSACTION_COMPLETE，会进一步触发 binder_thread_read 方法来处理这个消息。

binder_thread_read 把刚才的消息返回给源线程，进入到 waitForResponse 方法，这个方法收到后，再一次进入 while 循环，重新调用 talkWithDriver 进入 binder 驱动，等到后续的消息。