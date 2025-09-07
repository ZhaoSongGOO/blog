# Binder 死亡通知

在理想情况下，通过智能指针技术，以及 BR_INCREFS、BR_ACQUIRE、BR_DECREFS、BR_RELEASE、BC_ACQUIRE、BC_INCREFS、BC_RELEASE 和 BC_DECREFS 八个协议就可以正确地维护 Binder 进程间通信机制中各个 Binder 对象的生命周期。然而，在实际情况中，由于 Client 进程和 Server 进程在运行过程中可能会因为内部错误而异常退出，因此，运行在它们里面的 Binder 代理对象和 Binder 本地对象就会意外死亡，从而导致 Binder 进程间通信机制不能正确地维护它们与其他 Binder 对象的依赖关系。其中，最严重的是 Binder 本地对象的意外死亡，会导致依赖于它的 Binder 代理对象变得无效。

Binder 对象死亡通知机制，它可以监控到 Binder 本地对象的死亡事件，然后通知那些引用了它的 Binder 代理对象，从而在一定程度上解决无效 Binder 代理对象的问题。在这种死亡通知机制中，首先是 Binder 代理对象将一个死亡接收通知注册到 Binder 驱动程序中，然后当 Binder 驱动程序监控到它引用的 Binder 本地对象死亡时，Binder 驱动程序就会向它发送一个死亡通知。另外，当一个 Binder 代理对象不需要接收它所引用的 Binder本地对象的死亡通知时，它也可以注销之前所注册的死亡接收通知。

## 注册死亡接收通知

我们从 c++ binder 库中开始分析，首先用户需要先构造一个死亡通知接收者，这个接收者必须继承自 `IBinder::DeatchRecipient` 对象，并重写 binderDied 方法，当 Binder 驱动程序通知一个 Binder 代理对象它所引用的 Binder 本地对象已经死亡时，就会调用它所指定的死亡通知接收者的成员函数 binderDied。

```cpp
class IBinder:public virtual RefBase{
    //...
    class DeathRecipient : public virtual RefBase
    {
    public:
        virtual void binderDied(const wp<IBinder>& who) = 0;
    };
    //...
};
```

定义好死亡通知接收者之后，我们就可以调用 Binder 代理对象的成员函数 linkToDeath 来注册一个死亡接收通知了。

```cpp
status_t BpBinder::linkToDeath(
    const sp<DeathRecipient>& recipient, void* cookie, uint32_t flags)
{
    Obituary ob;
    ob.recipient = recipient;
    ob.cookie = cookie;
    ob.flags = flags;

    LOG_ALWAYS_FATAL_IF(recipient == NULL,
                        "linkToDeath(): recipient must be non-NULL");

    {
        AutoMutex _l(mLock);
        // 判断对应的服务是不是已经反馈了 death 消息，如果已经反馈了，就别注册了，直接返回 DEAD_OBJECT
        if (!mObitsSent) {
            if (!mObituaries) {
                // 只有第一次注册，才会真正和 binder 驱动交互，注册接收。参数使用的是注册死亡接收通知的Binder代理对象的句柄值和地址值。
                mObituaries = new Vector<Obituary>;
                if (!mObituaries) {
                    return NO_MEMORY;
                }
                LOGV("Requesting death notification: %p handle %d\n", this, mHandle);
                getWeakRefs()->incWeak(this);
                IPCThreadState* self = IPCThreadState::self();
                // 准备好注册监听的 binder 消息
                self->requestDeathNotification(mHandle, this);
                // 将消息同步到 binder 驱动。
                self->flushCommands();
            }
            ssize_t res = mObituaries->add(ob);
            return res >= (ssize_t)NO_ERROR ? (status_t)NO_ERROR : res;
        }
    }

    return DEAD_OBJECT;
}
```

现在，我们进入 binder 驱动中看下，binder 驱动是如何处理注册死亡监听消息的。

```c
int
binder_thread_write(struct binder_proc *proc, struct binder_thread *thread,
		    void __user *buffer, int size, signed long *consumed) {
                //...
		case BC_REQUEST_DEATH_NOTIFICATION:
		case BC_CLEAR_DEATH_NOTIFICATION: {
			uint32_t target;
			void __user *cookie;
			struct binder_ref *ref;
			struct binder_ref_death *death;
            // 取出 handler 值
			if (get_user(target, (uint32_t __user *)ptr))
				return -EFAULT;
			ptr += sizeof(uint32_t);
            // 取出 cookie，其实就是 BpBinder 的地址
			if (get_user(cookie, (void __user * __user *)ptr))
				return -EFAULT;
			ptr += sizeof(void *);
            // 进程中通过 handler 从 红黑树中拿到 binder_ref
			ref = binder_get_ref(proc, target);
			if (ref == NULL) {
				binder_user_error("binder: %d:%d %s "
					"invalid ref %d\n",
					proc->pid, thread->pid,
					cmd == BC_REQUEST_DEATH_NOTIFICATION ?
					"BC_REQUEST_DEATH_NOTIFICATION" :
					"BC_CLEAR_DEATH_NOTIFICATION",
					target);
				break;
			}

			if (binder_debug_mask & BINDER_DEBUG_DEATH_NOTIFICATION)
				printk(KERN_INFO "binder: %d:%d %s %p ref %d desc %d s %d w %d for node %d\n",
				       proc->pid, thread->pid,
				       cmd == BC_REQUEST_DEATH_NOTIFICATION ?
				       "BC_REQUEST_DEATH_NOTIFICATION" :
				       "BC_CLEAR_DEATH_NOTIFICATION",
				       cookie, ref->debug_id, ref->desc,
				       ref->strong, ref->weak, ref->node->debug_id);

			if (cmd == BC_REQUEST_DEATH_NOTIFICATION) {
                // 如果已经注册过了，报错
				if (ref->death) {
					binder_user_error("binder: %d:%"
						"d BC_REQUEST_DEATH_NOTI"
						"FICATION death notific"
						"ation already set\n",
						proc->pid, thread->pid);
					break;
				}
				death = kzalloc(sizeof(*death), GFP_KERNEL);
				if (death == NULL) {
					thread->return_error = BR_ERROR;
					if (binder_debug_mask & BINDER_DEBUG_FAILED_TRANSACTION)
						printk(KERN_INFO "binder: %d:%d "
							"BC_REQUEST_DEATH_NOTIFICATION failed\n",
							proc->pid, thread->pid);
					break;
				}
				binder_stats.obj_created[BINDER_STAT_DEATH]++;
				INIT_LIST_HEAD(&death->work.entry);
                // 注册死亡监听
				death->cookie = cookie;
				ref->death = death;
				if (ref->node->proc == NULL) {
                    // 如果注册的时候，服务已经死亡。。就将一个类型为BINDER_WORK_DEAD_BINDER的
                    // binder_ref_death 本身就是一个 binder_work.
                    // 工作项添加到当前线程或者当前线程所在的Client进程的todo队列中，以便可以向Client进程发送一个死亡接收通知。
					ref->death->work.type = BINDER_WORK_DEAD_BINDER;
                    // 首先看当前线程是不是 binder 线程，如果是的话，直接发送消息到当前线程的队列。否则发送到当前进程的队列中。
					if (thread->looper & (BINDER_LOOPER_STATE_REGISTERED | BINDER_LOOPER_STATE_ENTERED)) {
						list_add_tail(&ref->death->work.entry, &thread->todo);
					} else {
						list_add_tail(&ref->death->work.entry, &proc->todo);
						wake_up_interruptible(&proc->wait);
					}
				}
			} else {
				//...
			}
		} break;
        //...
}
```

## 发送死亡接收通知

Server 进程本来是应该常驻在系统中为 Client 进程提供服务的，但是可能会出现意外情况，导致它异常退出。Server 进程一旦异常退出之后，运行在它里面的 Binder 本地对象就意外死亡了。这时候 Binder 驱动程序就应该向那些引用了它的 Binder 代理对象发送死亡接收通知，以便它们可以知道自己引用了一个无效的 Binder 本地对象。

当 Server 进程退出后，要么自己 close /dev/binder 文件，要么交由操作系统去关闭，无论那种方法，都会触发到 binder 驱动的 binder_release 方法，内容如下。

```c
static int binder_release(struct inode *nodp, struct file *filp)
{
	struct binder_proc *proc = filp->private_data;
	if (binder_proc_dir_entry_proc) {
		char strbuf[11];
		snprintf(strbuf, sizeof(strbuf), "%u", proc->pid);
		remove_proc_entry(strbuf, binder_proc_dir_entry_proc);
	}

	binder_defer_work(proc, BINDER_DEFERRED_RELEASE);
	
	return 0;
}
```

随后，这个方法会触发 binder_deferred_release 方法。

```c
static void binder_deferred_release(struct binder_proc *proc) {
    //...
    while ((n = rb_first(&proc->nodes))) {
		struct binder_node *node = rb_entry(n, struct binder_node, rb_node);

		nodes++;
		rb_erase(&node->rb_node, &proc->nodes);
		list_del_init(&node->work.entry);
		if (hlist_empty(&node->refs)) {
			kfree(node);
			binder_stats.obj_deleted[BINDER_STAT_NODE]++;
		} else {
            // 如果 binder_node 的引用列表不为空
			struct binder_ref *ref;
			int death = 0;

			node->proc = NULL;
			node->local_strong_refs = 0;
			node->local_weak_refs = 0;
			hlist_add_head(&node->dead_node, &binder_dead_nodes);

			hlist_for_each_entry(ref, pos, &node->refs, node_entry) {
				incoming_refs++;
                // 如果 ref 注册了死亡监听
				if (ref->death) {
					death++;
					if (list_empty(&ref->death->work.entry)) {
						ref->death->work.type = BINDER_WORK_DEAD_BINDER;
                        // 把死亡监听消息发送到目标进程的 todo 队列
						list_add_tail(&ref->death->work.entry, &ref->proc->todo);
                        // 唤醒目标进程的 binder_thread_read 方法
						wake_up_interruptible(&ref->proc->wait);
					} else
						BUG();
				}
			}
			if (binder_debug_mask & BINDER_DEBUG_DEAD_BINDER)
				printk(KERN_INFO "binder: node %d now dead, refs %d, death %d\n", node->debug_id, incoming_refs, death);
		}
	}
    //...
}

```

目标进程的 binder_thread_read 方法触发后，从队列中取出来刚才的事件。

```c
static int
binder_thread_read(struct binder_proc *proc, struct binder_thread *thread,
	void  __user *buffer, int size, signed long *consumed, int non_block) {
        //...
		case BINDER_WORK_DEAD_BINDER:
		case BINDER_WORK_DEAD_BINDER_AND_CLEAR:
		case BINDER_WORK_CLEAR_DEATH_NOTIFICATION: {
            // 复原出 binder_ref_death
			struct binder_ref_death *death = container_of(w, struct binder_ref_death, work);
			uint32_t cmd;
			if (w->type == BINDER_WORK_CLEAR_DEATH_NOTIFICATION)
				cmd = BR_CLEAR_DEATH_NOTIFICATION_DONE;
			else
				cmd = BR_DEAD_BINDER;
            // 把操作码写入用户空间
			if (put_user(cmd, (uint32_t __user *)ptr))
				return -EFAULT;
			ptr += sizeof(uint32_t);
            // cookie 是 BpBinder 的地址，写入到用户空间。
			if (put_user(death->cookie, (void * __user *)ptr))
				return -EFAULT;
			ptr += sizeof(void *);
			if (binder_debug_mask & BINDER_DEBUG_DEATH_NOTIFICATION)
				printk(KERN_INFO "binder: %d:%d %s %p\n",
				       proc->pid, thread->pid,
				       cmd == BR_DEAD_BINDER ?
				       "BR_DEAD_BINDER" :
				       "BR_CLEAR_DEATH_NOTIFICATION_DONE",
				       death->cookie);

			if (w->type == BINDER_WORK_CLEAR_DEATH_NOTIFICATION) {
				list_del(&w->entry);
				kfree(death);
				binder_stats.obj_deleted[BINDER_STAT_DEATH]++;
			} else
				list_move(&w->entry, &proc->delivered_death);
			if (cmd == BR_DEAD_BINDER)
				goto done; /* DEAD_BINDER notifications can cause transactions */
		} break;
        //...
}
```

随后，回到用户空间，计入到 IPCThreadState::executeCommand 方法中。

```cpp
status_t IPCThreadState::executeCommand(int32_t cmd) {
    //...
    case BR_DEAD_BINDER:
        {
            BpBinder *proxy = (BpBinder*)mIn.readInt32();
            proxy->sendObituary(); // 发送死亡通知
            mOut.writeInt32(BC_DEAD_BINDER_DONE);
            mOut.writeInt32((int32_t)proxy); // 通知 binder 驱动，我已经处理完 binder 死亡通知。
        } break;
    //...
}
```

进一步挖掘下 sendObituary。

```cpp
void BpBinder::sendObituary()
{
    LOGV("Sending obituary for proxy %p handle %d, mObitsSent=%s\n",
        this, mHandle, mObitsSent ? "true" : "false");

    mAlive = 0;
    if (mObitsSent) return;

    mLock.lock();
    Vector<Obituary>* obits = mObituaries;
    // 既然已经收到死亡监听，后续也不会收到了，那就取消死亡监听吧
    if(obits != NULL) {
        LOGV("Clearing sent death notification: %p handle %d\n", this, mHandle);
        IPCThreadState* self = IPCThreadState::self();
        self->clearDeathNotification(mHandle, this);
        self->flushCommands();
        mObituaries = NULL;
    }
    mObitsSent = 1;
    mLock.unlock();

    LOGV("Reporting death of proxy %p for %d recipients\n",
        this, obits ? obits->size() : 0);
    // 遍历用户注册的死亡监听接收者
    if (obits != NULL) {
        const size_t N = obits->size();
        for (size_t i=0; i<N; i++) {
            reportOneDeath(obits->itemAt(i));
        }

        delete obits;
    }
}

void BpBinder::reportOneDeath(const Obituary& obit)
{
    sp<DeathRecipient> recipient = obit.recipient.promote();
    LOGV("Reporting death to recipient: %p\n", recipient.get());
    if (recipient == NULL) return;
    // 触发对应的 binderDied 接口。
    recipient->binderDied(this);    
}
```

## 注销死亡接收通知


在某一个死亡监听接收者想注销的时候，就会调用 BpBinder 的  unlinkToDeath 方法。

```cpp
status_t BpBinder::unlinkToDeath(
    const wp<DeathRecipient>& recipient, void* cookie, uint32_t flags,
    wp<DeathRecipient>* outRecipient)
{
    AutoMutex _l(mLock);

    // 如果已经收到死亡监听了，则不需要处理，因为从上面也可以看到，收到死亡监听后，会自动发送取消监听的操作。
    if (mObitsSent) {
        return DEAD_OBJECT;
    }

    const size_t N = mObituaries ? mObituaries->size() : 0;
    for (size_t i=0; i<N; i++) {
        const Obituary& obit = mObituaries->itemAt(i);
        if ((obit.recipient == recipient
                    || (recipient == NULL && obit.cookie == cookie))
                && obit.flags == flags) {
            const uint32_t allFlags = obit.flags|flags;
            if (outRecipient != NULL) {
                *outRecipient = mObituaries->itemAt(i).recipient;
            }
            mObituaries->removeAt(i);
            if (mObituaries->size() == 0) {
                // 如果发现用户已经取消了所有的死亡监听接收者，那就发送取消死亡监听的操作
                LOGV("Clearing death notification: %p handle %d\n", this, mHandle);
                IPCThreadState* self = IPCThreadState::self();
                self->clearDeathNotification(mHandle, this);
                self->flushCommands();
                delete mObituaries;
                mObituaries = NULL;
            }
            return NO_ERROR;
        }
    }

    return NAME_NOT_FOUND;
}

status_t IPCThreadState::clearDeathNotification(int32_t handle, BpBinder* proxy)
{   
    // 注销死亡监听的本质就是给binder驱动发送了一个消息，传入handle 和 BpBinder 的地址。
    mOut.writeInt32(BC_CLEAR_DEATH_NOTIFICATION);
    mOut.writeInt32((int32_t)handle);
    mOut.writeInt32((int32_t)proxy);
    return NO_ERROR;
}
```

这个消息和注册死亡监听消息一样，会发送到 binder_thread_write 方法。

```c
int
binder_thread_write(struct binder_proc *proc, struct binder_thread *thread,
		    void __user *buffer, int size, signed long *consumed) {
                //...
		case BC_REQUEST_DEATH_NOTIFICATION:
		case BC_CLEAR_DEATH_NOTIFICATION: {
			uint32_t target;
			void __user *cookie;
			struct binder_ref *ref;
			struct binder_ref_death *death;
            // 取出 handler 值
			if (get_user(target, (uint32_t __user *)ptr))
				return -EFAULT;
			ptr += sizeof(uint32_t);
            // 取出 cookie，其实就是 BpBinder 的地址
			if (get_user(cookie, (void __user * __user *)ptr))
				return -EFAULT;
			ptr += sizeof(void *);
            // 进程中通过 handler 从 红黑树中拿到 binder_ref
			ref = binder_get_ref(proc, target);
			if (ref == NULL) {
				binder_user_error("binder: %d:%d %s "
					"invalid ref %d\n",
					proc->pid, thread->pid,
					cmd == BC_REQUEST_DEATH_NOTIFICATION ?
					"BC_REQUEST_DEATH_NOTIFICATION" :
					"BC_CLEAR_DEATH_NOTIFICATION",
					target);
				break;
			}

			if (binder_debug_mask & BINDER_DEBUG_DEATH_NOTIFICATION)
				printk(KERN_INFO "binder: %d:%d %s %p ref %d desc %d s %d w %d for node %d\n",
				       proc->pid, thread->pid,
				       cmd == BC_REQUEST_DEATH_NOTIFICATION ?
				       "BC_REQUEST_DEATH_NOTIFICATION" :
				       "BC_CLEAR_DEATH_NOTIFICATION",
				       cookie, ref->debug_id, ref->desc,
				       ref->strong, ref->weak, ref->node->debug_id);

			if (cmd == BC_REQUEST_DEATH_NOTIFICATION) {
                //...
			} else {
				if (ref->death == NULL) {
					binder_user_error("binder: %d:%"
						"d BC_CLEAR_DEATH_NOTIFI"
						"CATION death notificat"
						"ion not active\n",
						proc->pid, thread->pid);
					break;
				}
				death = ref->death;
				if (death->cookie != cookie) {
					binder_user_error("binder: %d:%"
						"d BC_CLEAR_DEATH_NOTIFI"
						"CATION death notificat"
						"ion cookie mismatch "
						"%p != %p\n",
						proc->pid, thread->pid,
						death->cookie, cookie);
					break;
				}
                // 注销就很简单，直接置空 death 字段
				ref->death = NULL;
				// 判断这个 binder_ref_death 是不是已经在一个队列中被关联了
				/*
					static inline int list_empty(const struct list_head *head)
					{
						return head->next == head;
					}
				*/
				if (list_empty(&death->work.entry)) {
					death->work.type = BINDER_WORK_CLEAR_DEATH_NOTIFICATION;
                    // 向当前线程或者当前线程所属的Client进程的todo队列中添加一个类型为BINDER_WORK_CLEAR_DEATH_NOTIFICATION或者
                    // BINDER_WORK_DEAD_BINDER_AND_CLEAR的工作项，用来描述死亡接收通知注销操作的结果，并且返回给Client进程。
					if (thread->looper & (BINDER_LOOPER_STATE_REGISTERED | BINDER_LOOPER_STATE_ENTERED)) {
						list_add_tail(&death->work.entry, &thread->todo);
					} else {
						list_add_tail(&death->work.entry, &proc->todo);
						wake_up_interruptible(&proc->wait);
					}
				} else {
					BUG_ON(death->work.type != BINDER_WORK_DEAD_BINDER);
					death->work.type = BINDER_WORK_DEAD_BINDER_AND_CLEAR;
				}
			}
		} break;
        //...
}
```
