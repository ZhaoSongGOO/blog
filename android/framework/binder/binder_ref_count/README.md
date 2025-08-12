# Binder 对象引用计数技术

## Binder 本地对象的生命周期


Binder 本地对象是一个 BBinder 的子类，在用户空间常见，并运行在 Server 进程中。Binder 本地对象一方面会被 Server 进程中其他对象引用，另一方面也会被 Binder 驱动中的 Binder 实体对象 binder_node 引用。

对于 Server 进程中的对象可以使用 RefBase 只能指针来管理生命周期，但是 binder 驱动程序没法这样做，所以定义了一个新的规则来避免它们还在被 binder_node 引用时销毁的问题。

Server 进程将一个 Binder 本地对象注册到 ServerManager 时，Binder 驱动程序就会为它创建一个 Binder 实体对象。接下来，当 Client 进程通过 Service Manager 来查询一个 Binder 本地对象的代理对象接口时，Binder 驱动程序就会为它所对应的 Binder 实体对象创建一个 Binder 引用对象， 接着再使用 `BR_INCREFS` 和 `BR_ACQUIRE` 协议来通知对应的 Server 进程增加对应的 Binder 本地对象的弱引用计数和强引用计数。这样就能保证 Client 进程中的 Binder 代理对象在引用一个 Binder本地对象期间，该 Binder 本地对象不会被销毁。

当没有任何 Binder 代理对象引用一个 Binder 本地对象时，Binder 驱动程序就会使用 `BR_DECREFS` 和 `BR_RELEASE` 协议来通知对应的 Server 进程减少对应的Binder本地对象的弱引用计数和强引用计数。

这些增加强弱引用计数的信息会被包装成一个类型为 BINDER_WORK_NODE 的 binder_work 放到目标进程的 todo 队列中。这个 binder_work 的具体实现是 binder_node 节点。

Server 进程使用 ioctl 监听事件请求的时候，会阻塞到 binder_thread_read 这个调用上，直到有任务出现，对于当前场景，就是一个 BINDER_WORK_NODE 类型的任务。

代码逻辑如下。

```c
static int
binder_thread_read(struct binder_proc *proc, struct binder_thread *thread,
	void  __user *buffer, int size, signed long *consumed, int non_block) {
        //...
        while(1){
        //...
		case BINDER_WORK_NODE: {
            // 从 binder_work 成员拿到 binder_node 结构体
			struct binder_node *node = container_of(w, struct binder_node, work);
			uint32_t cmd = BR_NOOP;
			const char *cmd_name;
            // 如果当前节点有强引用场景
			int strong = node->internal_strong_refs || node->local_strong_refs;
            // 如果当前节点有弱引用场景
			int weak = !hlist_empty(&node->refs) || node->local_weak_refs || strong;
            // 如果有弱引用但是还没有增加 binder 本地对象的弱引用计数
			if (weak && !node->has_weak_ref) {
				cmd = BR_INCREFS;
				cmd_name = "BR_INCREFS";
				node->has_weak_ref = 1;
				node->pending_weak_ref = 1;
				node->local_weak_refs++;
			} else if (strong && !node->has_strong_ref) {
                // 如果有强引用但是还没有增加 binder 本地对象的强引用计数
				cmd = BR_ACQUIRE;
				cmd_name = "BR_ACQUIRE";
				node->has_strong_ref = 1;
				node->pending_strong_ref = 1;
				node->local_strong_refs++;
			} else if (!strong && node->has_strong_ref) {
                // 如果没有强引用了，而且还没解除 binder 本地对象的强应用计数
				cmd = BR_RELEASE;
				cmd_name = "BR_RELEASE";
				node->has_strong_ref = 0;
			} else if (!weak && node->has_weak_ref) {
                // 如果没有弱引用了，而且还没解除 binder 本地对象的弱应用计数
				cmd = BR_DECREFS;
				cmd_name = "BR_DECREFS";
				node->has_weak_ref = 0;
			}
			if (cmd != BR_NOOP) {
                // 把 cmd、ptr、cookie 这三个存储在用户空间的一个存储区。
                // ptr 和 cookie 指向两个用户空间的地址，其中，成员变量cookie指向该Service组件的地址，
                // 而成员变量ptr指向该Service组件内部的一个引用计数对象（类型为weakref_impl）的地址。
				if (put_user(cmd, (uint32_t __user *)ptr))
					return -EFAULT;
				ptr += sizeof(uint32_t);
				if (put_user(node->ptr, (void * __user *)ptr))
					return -EFAULT;
				ptr += sizeof(void *);
				if (put_user(node->cookie, (void * __user *)ptr))
					return -EFAULT;
				ptr += sizeof(void *);

				binder_stat_br(proc, thread, cmd);
				if (binder_debug_mask & BINDER_DEBUG_USER_REFS)
					printk(KERN_INFO "binder: %d:%d %s %d u%p c%p\n",
					       proc->pid, thread->pid, cmd_name, node->debug_id, node->ptr, node->cookie);
			} else {
                //...
			}
		} break;
        }
        //...
}
```

Server 进程在 ioctl 解除阻塞后，使用了 Binder 库中 IPCThreadState 的 executeCommand 接口来处理驱动程序发送的协议。

这个函数里面会通过内核在用户空间存储的 ptr 和 cookie 找到对应的 binder 对象。

对于 BR_ACQUIRE 和 BR_INCREFS 这种增加引用计数的任务，立刻执行，因为增加一个 Binder 本地对象的引用计数是一件紧急的事情，必须要马上处理。

对于 BR_DECREFS 和 BR_RELEASE 这种减少引用计数的任务，则是放到一个队列中，等到 Server 进程下次使用 IO 控制命令 BINDER_WRITE_READ 进入 Binder 驱动程序之前，再来处理它们。

```cpp
status_t IPCThreadState::executeCommand(int32_t cmd)
{
    BBinder* obj;
    RefBase::weakref_type* refs;
    status_t result = NO_ERROR;
    
    switch (cmd) {
    case BR_ERROR:
        result = mIn.readInt32();
        break;
        
    case BR_OK:
        break;
        
    case BR_ACQUIRE: 
        // 通过 ptr 和 cookie 来确定修改哪一个对象的引用计数
        refs = (RefBase::weakref_type*)mIn.readInt32();
        obj = (BBinder*)mIn.readInt32();
        LOG_ASSERT(refs->refBase() == obj,
                   "BR_ACQUIRE: object %p does not match cookie %p (expected %p)",
                   refs, obj, refs->refBase());
        obj->incStrong(mProcess.get());
        IF_LOG_REMOTEREFS() {
            LOG_REMOTEREFS("BR_ACQUIRE from driver on %p", obj);
            obj->printRefs();
        }
        mOut.writeInt32(BC_ACQUIRE_DONE);
        mOut.writeInt32((int32_t)refs);
        mOut.writeInt32((int32_t)obj);
        break;
        
    case BR_INCREFS:
        refs = (RefBase::weakref_type*)mIn.readInt32();
        obj = (BBinder*)mIn.readInt32();
        refs->incWeak(mProcess.get());
        mOut.writeInt32(BC_INCREFS_DONE);
        mOut.writeInt32((int32_t)refs);
        mOut.writeInt32((int32_t)obj);
        break;

    case BR_RELEASE:
        refs = (RefBase::weakref_type*)mIn.readInt32();
        obj = (BBinder*)mIn.readInt32();
        LOG_ASSERT(refs->refBase() == obj,
                   "BR_RELEASE: object %p does not match cookie %p (expected %p)",
                   refs, obj, refs->refBase());
        IF_LOG_REMOTEREFS() {
            LOG_REMOTEREFS("BR_RELEASE from driver on %p", obj);
            obj->printRefs();
        }
        mPendingStrongDerefs.push(obj);
        break;
        
    case BR_DECREFS:
        refs = (RefBase::weakref_type*)mIn.readInt32();
        obj = (BBinder*)mIn.readInt32();
        // NOTE: This assertion is not valid, because the object may no
        // longer exist (thus the (BBinder*)cast above resulting in a different
        // memory address).
        //LOG_ASSERT(refs->refBase() == obj,
        //           "BR_DECREFS: object %p does not match cookie %p (expected %p)",
        //           refs, obj, refs->refBase());
        mPendingWeakDerefs.push(refs);
        break;
    //...
    }
    //...
}
```

## Binder 实体对象 binder_node 的生命周期

Binder 实体对象是一个类型为 binder_node 的对象，它是在 Binder 驱动程序中创建的，并且被 Binder 驱动程序中的 Binder 引用对象所引用。当 Client 进程第一次引用一个 Binder 实体对象时，Binder 驱动程序就会在内部为它创建一个 Binder 引用对象。例如，当 Client 进程通过 Service Manager 来获得一个 Service 组件的代理对象接口时，Binder 驱动程序就会找到与该 Service 组件对应的 Binder 实体对象，接着再创建一个 Binder 引用对象来引用它。这时候就需要增加被引用的 Binder 实体对象的引用计数。

相应地，当 Client 进程不再引用一个 Service 组件时，它也会请求 Binder 驱动程序释放之前为它所创建的一个 Binder 引用对象。这时候就需要减少该 Binder 引用对象所引用的 Binder 实体对象的引用计数。

以前我们介绍过了，每一个 binder_node 内部都有三个引用计数，分别是 internal_strong_refs、local_strong_refs、local_weak_refs。

其中 internal_strong_refs 记录的是 binder 驱动内部其余结构对于当前 binder_node 的强引用计数。

local_strong_refs 和 local_weak_refs 描述的是 binder_node 所属进程内，用户空间对于 binder_node 的引用。

而 client 对于 binder_node 引用不会直接反映在这两个上面，而是通过 binder_ref 来间接引用。

更进一步的解释，在 Binder 的生命周期管理中，`binder_node` 结构体通过三组引用计数来精确追踪其状态：

1. 本地引用 (`local_strong_refs`, `local_weak_refs`): 这两个计数严格反映了服务提供方进程（Server Process）的用户空间对本地 Binder 实体（如 `BBinder`）的引用情况。当 `local_strong_refs` 降为 0 时，意味着 Server 进程自身已不再需要此对象，驱动会通知用户空间可以销毁它。

2. 内部引用 (`internal_strong_refs`): 此计数代表 Binder 驱动内部对 `binder_node` 的强引用。它的主要来源是客户端的间接引用：当任何一个客户端进程通过其 `binder_ref` 结构持有对该 `binder_node` 的强引用时，`internal_strong_refs` 就会增加。此外，正在进行的 Binder 事务也可能短暂地持有该引用。只要此计数大于 0，`binder_node` 就不会被销毁，因为它仍在被内核或其他进程使用。

3. 客户端间接引用 (通过 `binder_ref`): 客户端对服务的引用并不直接作用于 `binder_node`，而是通过一个位于客户端进程上下文中的 `binder_ref` 结构来实现。客户端的每次强引用/弱引用操作，都只改变其对应 `binder_ref` 的引用计数。而 `binder_ref` 的引用计数变化（尤其是从 0 到 1 或从 1 到 0 的临界点），才会进一步去修改 `binder_node` 的 `internal_strong_refs`，从而完成了这种跨进程的、解耦的生命周期管理。

```c
/*
node: 要增加引用计数的 Binder 实体对象。
strong: 增加强引用还是弱引用？
internal: 区分是内部引用还是外部引用计数。
target_list: 指向一个目标进程或者目标线程的 todo 队列，表示增加 binder_node 引用计数后，要相应增加 binder 本地对象的引用
*/
static int
binder_inc_node(struct binder_node *node, int strong, int internal,
		struct list_head *target_list)
{
	if (strong) {
		if (internal) {
			if (target_list == NULL &&
			    node->internal_strong_refs == 0 &&
			    !(node == binder_context_mgr_node &&
			    node->has_strong_ref)) {
				printk(KERN_ERR "binder: invalid inc strong "
					"node for %d\n", node->debug_id);
				return -EINVAL;
			}
			node->internal_strong_refs++;
		} else
			node->local_strong_refs++;
		if (!node->has_strong_ref && target_list) {
            // 如果当前节点还没有对 binder 本地对象设置强引用，就加入到对应的任务队列中，Binder 驱动稍后会遍历这个列表，向用户空间发
            // 送 `BR_INCREFS` 或 `BR_WEAK_ACQUIRE` 等通知。通常这个 `target_list` 就是 `binder_proc->todo`。
			list_del_init(&node->work.entry);
			list_add_tail(&node->work.entry, target_list);
		}
	} else {
		if (!internal)
			node->local_weak_refs++;
		if (!node->has_weak_ref && list_empty(&node->work.entry)) {
			if (target_list == NULL) {
				printk(KERN_ERR "binder: invalid inc weak node "
					"for %d\n", node->debug_id);
				return -EINVAL;
			}
			list_add_tail(&node->work.entry, target_list);
		}
	}
	return 0;
}
```

下面列举了 binder_node 减少引用计数的逻辑。

```c
static int
binder_dec_node(struct binder_node *node, int strong, int internal)
{
	if (strong) {
		if (internal)
			node->internal_strong_refs--;
		else
			node->local_strong_refs--;
		if (node->local_strong_refs || node->internal_strong_refs)
			return 0;
	} else {
		if (!internal)
			node->local_weak_refs--;
		if (node->local_weak_refs || !hlist_empty(&node->refs))
			return 0;
	}
    // Binder 实体对象 node 的强引用计数或者弱引用计数等于 0 了
    // 如果之前增加过对于 binder 本地对象的引用，所以这里需要减少对其的引用。
	if (node->proc && (node->has_strong_ref || node->has_weak_ref)) {
		if (list_empty(&node->work.entry)) {
			list_add_tail(&node->work.entry, &node->proc->todo);
			wake_up_interruptible(&node->proc->wait);
		}
	} else {
        // 如果没有任何的强弱引用，销毁这个 node
		if (hlist_empty(&node->refs) && !node->local_strong_refs &&
		    !node->local_weak_refs) {
			list_del_init(&node->work.entry);
			if (node->proc) {
				rb_erase(&node->rb_node, &node->proc->nodes);
				if (binder_debug_mask & BINDER_DEBUG_INTERNAL_REFS)
					printk(KERN_INFO "binder: refless node %d deleted\n", node->debug_id);
			} else {
				hlist_del(&node->dead_node);
				if (binder_debug_mask & BINDER_DEBUG_INTERNAL_REFS)
					printk(KERN_INFO "binder: dead node %d deleted\n", node->debug_id);
			}
			kfree(node);
			binder_stats.obj_deleted[BINDER_STAT_NODE]++;
		}
	}

	return 0;
}
```



