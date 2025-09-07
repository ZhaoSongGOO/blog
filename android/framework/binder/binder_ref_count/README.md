# Binder 对象引用计数技术

## Binder 本地对象的生命周期


Binder 本地对象是一个 BBinder 的子类，在用户空间常见，并运行在 Server 进程中。Binder 本地对象一方面会被 Server 进程中其他对象引用，另一方面也会被 Binder 驱动中的 Binder 实体对象 binder_node 引用。

对于 Server 进程中的对象可以使用 RefBase 智能指针来管理生命周期，但是 binder 驱动程序没法这样做，所以定义了一个新的规则来避免它们还在被 binder_node 引用时销毁的问题。

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

## Binder 引用对象 binder_ref 的生命周期

Binder 引用对象是一个类型为 binder_ref 的对象，它是在 Binder 驱动程序中创建的，并且被用户空间中的 Binder 代理对象所引用。当 Client 进程引用了 Server 进程中的一个 Binder 本地对象时，Binder 驱动程序就会在内部为它创建一个 Binder 引用对象。由于 Binde 引用对象是运行在内核空间的，而引用了它的 Binder 代理对象是运行在用户空间的，因此，Client 进程和 Binder 驱动程序就需要约定一套规则来维护 Binder 引用对象的引用计数，避免它们在还被 Binder 代理对象引用的情况下被销毁。

这套规则可以划分为 BC_ACQUIRE、BC_INCREFS、BC_RELEASE 和 BC_DECREFS 四个协议，分别用来增加和减少一个 Binder 引用对象的强引用计数和弱引用计数。

```c
// // ret = binder_thread_write(proc, thread, (void __user *)bwr.write_buffer, bwr.write_size, &bwr.write_consumed);
// 这里面 buffer 参数是 binder_write_read 结构体里面的 write_buffer
int
binder_thread_write(struct binder_proc *proc, struct binder_thread *thread,
		    void __user *buffer, int size, signed long *consumed)
{
	uint32_t cmd;
	void __user *ptr = buffer + *consumed;
	void __user *end = buffer + size;

	while (ptr < end && thread->return_error == BR_OK) {
		// 对于一个 binder_write_read 里面的buffer 中，第一位是 cmd
		if (get_user(cmd, (uint32_t __user *)ptr))
			return -EFAULT;
		ptr += sizeof(uint32_t);
		if (_IOC_NR(cmd) < ARRAY_SIZE(binder_stats.bc)) {
			binder_stats.bc[_IOC_NR(cmd)]++;
			proc->stats.bc[_IOC_NR(cmd)]++;
			thread->stats.bc[_IOC_NR(cmd)]++;
		}
		switch (cmd) {
		case BC_INCREFS:
		case BC_ACQUIRE:
		case BC_RELEASE:
		case BC_DECREFS: {
			uint32_t target;
			struct binder_ref *ref;
			const char *debug_string;
			// 这四种 cmd 对应的数据就是 Handle，也就是 binder_ref 的 desc。
			if (get_user(target, (uint32_t __user *)ptr))
				return -EFAULT;
			ptr += sizeof(uint32_t);
			if (target == 0 && binder_context_mgr_node &&
			    (cmd == BC_INCREFS || cmd == BC_ACQUIRE)) {
				ref = binder_get_ref_for_node(proc,
					       binder_context_mgr_node);
				if (ref->desc != target) {
					binder_user_error("binder: %d:"
						"%d tried to acquire "
						"reference to desc 0, "
						"got %d instead\n",
						proc->pid, thread->pid,
						ref->desc);
				}
			} else // 从红黑树中去除 binder_ref
				ref = binder_get_ref(proc, target);
			if (ref == NULL) {
				binder_user_error("binder: %d:%d refcou"
					"nt change on invalid ref %d\n",
					proc->pid, thread->pid, target);
				break;
			}
			// 根据指令选择性的对 ref 做增加引用计数的操作
			switch (cmd) {
			case BC_INCREFS:
				debug_string = "IncRefs";
				binder_inc_ref(ref, 0, NULL);
				break;
			case BC_ACQUIRE:
				debug_string = "Acquire";
				binder_inc_ref(ref, 1, NULL);
				break;
			case BC_RELEASE:
				debug_string = "Release";
				binder_dec_ref(ref, 1);
				break;
			case BC_DECREFS:
			default:
				debug_string = "DecRefs";
				binder_dec_ref(ref, 0);
				break;
			}
			if (binder_debug_mask & BINDER_DEBUG_USER_REFS)
				printk(KERN_INFO "binder: %d:%d %s ref %d desc %d s %d w %d for node %d\n",
				       proc->pid, thread->pid, debug_string, ref->debug_id, ref->desc, ref->strong, ref->weak, ref->node->debug_id);
			break;
		}
//...
		}
		//...
	}
	//...
}
```

首先我们看 `binder_inc_ref` 和 `binder_dec_ref` 的操作。

```c
static int
binder_inc_ref(
	struct binder_ref *ref, int strong, struct list_head *target_list)
{
	int ret;
	if (strong) {
		// 如果是强引用计数，而且是首次增加强引用计数，那还要增加对应的 binder_node 的强引用计数，而且是 internal 的。
		if (ref->strong == 0) {
			ret = binder_inc_node(ref->node, 1, 1, target_list);
			if (ret)
				return ret;
		}
		ref->strong++;
	} else {
		// 一样的，增加对应的 binder_node 的弱引用计数。
		if (ref->weak == 0) {
			ret = binder_inc_node(ref->node, 0, 1, target_list);
			if (ret)
				return ret;
		}
		ref->weak++;
	}
	return 0;
}

static int
binder_dec_ref(struct binder_ref *ref, int strong)
{
	if (strong) {
		if (ref->strong == 0) {
			binder_user_error("binder: %d invalid dec strong, "
					  "ref %d desc %d s %d w %d\n",
					  ref->proc->pid, ref->debug_id,
					  ref->desc, ref->strong, ref->weak);
			return -EINVAL;
		}
		ref->strong--;
		if (ref->strong == 0) {
			int ret;
			ret = binder_dec_node(ref->node, strong, 1);
			if (ret)
				return ret;
		}
	} else {
		if (ref->weak == 0) {
			binder_user_error("binder: %d invalid dec weak, "
					  "ref %d desc %d s %d w %d\n",
					  ref->proc->pid, ref->debug_id,
					  ref->desc, ref->strong, ref->weak);
			return -EINVAL;
		}
		ref->weak--;
	}
	// 如果自己的强弱引用计数都为 0, 那就删除自己
	if (ref->strong == 0 && ref->weak == 0)
		binder_delete_ref(ref);
	return 0;
}
```

我们再进一步看看 `binder_delete_ref` 操作的内容。

```c
static void
binder_delete_ref(struct binder_ref *ref)
{
	if (binder_debug_mask & BINDER_DEBUG_INTERNAL_REFS)
		printk(KERN_INFO "binder: %d delete ref %d desc %d for "
			"node %d\n", ref->proc->pid, ref->debug_id,
			ref->desc, ref->node->debug_id);
	// 从 binder_proc 的两棵红黑树上删除节点
	rb_erase(&ref->rb_node_desc, &ref->proc->refs_by_desc);
	rb_erase(&ref->rb_node_node, &ref->proc->refs_by_node);
	if (ref->strong)
		binder_dec_node(ref->node, 1, 1);
	// 从 binder_node 的列表中移除
	hlist_del(&ref->node_entry);
	binder_dec_node(ref->node, 0, 1);
	// 删除死亡接受通知
	if (ref->death) {
		if (binder_debug_mask & BINDER_DEBUG_DEAD_BINDER)
			printk(KERN_INFO "binder: %d delete ref %d desc %d "
				"has death notification\n", ref->proc->pid,
				ref->debug_id, ref->desc);
		list_del(&ref->death->work.entry);
		kfree(ref->death);
		binder_stats.obj_deleted[BINDER_STAT_DEATH]++;
	}
	// 析构
	kfree(ref);
	binder_stats.obj_deleted[BINDER_STAT_REF]++;
}
```

假设有三个 Binder 引用对象引用了一个 Binder 实体对象，其中，有两个 Binder 引用对象的强引用计数等于 3，另外一个 Binder 引用对象的强引用计数等于 1。每当一个 Binder 引用对象的强引用计数由 0 变为 1 时，它都会增加对应的 Binder 实体对象的外部强引用计数 internal_strong_refs。因此，Binder 实体对象的外部强引用计数 internal_strong_refs 等于 3，小于所有引用了它的 Binder 引用对象的强引用计数之和，即一个 Binder 引用对象的强引用计数与它所引用的 Binder 实体对象的外部强引用计数是多对一的关系。这样做的好处是可以减少执行修改 Binder 实体对象的引用计数的操作。

<img src="android/framework/binder/binder_ref_count/resources/1.png" style="width:50%">


## Binder 代理对象的生命周期

Binder 代理对象是一个类型为 BpBinder 的对象，它是在用户空间中创建的，并且运行在 client 进程中。与 Binder 本地对象类似，Binder 代理对象一方面会被运行在 client 进程的其他对象引用，另一方面它也会引用 Binder 驱动程序中的 Binder 引用对象。由于 BpBinder 类继承了 RefBase 类，因此，Client 进程中的其他对象可以简单地通过智能指针来引用这些 Binder 代理对象，以便可以控制它们的生命周期。由于 Binder 驱动程序中的 Binder 引用对象是运行在内核空间的，Binder 代理对象就不能通过智能指针来引用它们，因此，Client 进程就需要通过 BC_ACQUIRE、BC_INCREFS、BC_RELEASE 和 BC_DECREFS 四个协议来引用 Binder 驱动程序中的 Binder 引用对象。

即我们的 BpBinder 对象需要和 binder 驱动保持通信，以控制对 bider_ref 的引用，防止 binder_ref 被销毁。

在我们创建一个 BpBinder 的时候，构造函数中就会去增加 binder_ref 的弱引用计数。在析构函数中，也会再一次的消减对应 binder_ref 的弱引用计数。

```cpp
BpBinder::BpBinder(int32_t handle)
    : mHandle(handle)
    , mAlive(1)
    , mObitsSent(0)
    , mObituaries(NULL)
{
    LOGV("Creating BpBinder %p handle %d\n", this, mHandle);

    extendObjectLifetime(OBJECT_LIFETIME_WEAK);
    IPCThreadState::self()->incWeakHandle(handle); // 增加弱引用计数
}

void IPCThreadState::incWeakHandle(int32_t handle)
{
    LOG_REMOTEREFS("IPCThreadState::incWeakHandle(%d)\n", handle);
    mOut.writeInt32(BC_INCREFS);
    mOut.writeInt32(handle);
}

BpBinder::~BpBinder()
{
    LOGV("Destroying BpBinder %p handle %d\n", this, mHandle);

    IPCThreadState* ipc = IPCThreadState::self();

    //...

    if (ipc) {
        ipc->expungeHandle(mHandle, this);
        ipc->decWeakHandle(mHandle);
    }
}

void IPCThreadState::decWeakHandle(int32_t handle)
{
    LOG_REMOTEREFS("IPCThreadState::decWeakHandle(%d)\n", handle);
    mOut.writeInt32(BC_DECREFS);
    mOut.writeInt32(handle);
}
```

前面提到，一个 Binder 代理对象可能会被用户空间的其他对象引用，当其他对象通过强指针来引用这些 Binder 代理对象时，Client 进程就需要请求 Binder 驱动程序增加相应的 Binder 引用对象的强引用计数。为了减少 Client 进程和 Binder 驱动程序的交互开销，当一个 Binder 代理对象第一次被强指针引用时，Client 进程才会请求 Binder 驱动程序增加相应的 Binder 引用对象的强引用计数；同时，当一个 Binder 代理对象不再被任何强指针引用时，Client 进程就会请求 Binder 驱动程序减少相应的 Binder 引用对象的强引用计数。


Android RefBase 提供了两个回调，当一个对象第一次被强指针引用时，它的成员函数 onFirstRef 就会被调用；而当一个对象不再被任何强指针引用时，它的成员函数 onLastStrongRef 就会被调用。

下面展示 BpBinder 中这两个函数的实现。

```cpp
void BpBinder::onFirstRef()
{
    LOGV("onFirstRef BpBinder %p handle %d\n", this, mHandle);
    IPCThreadState* ipc = IPCThreadState::self();
    if (ipc) ipc->incStrongHandle(mHandle);
}

void IPCThreadState::incStrongHandle(int32_t handle)
{
    LOG_REMOTEREFS("IPCThreadState::incStrongHandle(%d)\n", handle);
    mOut.writeInt32(BC_ACQUIRE);
    mOut.writeInt32(handle);
}

void BpBinder::onLastStrongRef(const void* id)
{
    LOGV("onLastStrongRef BpBinder %p handle %d\n", this, mHandle);
    IF_LOGV() {
        printRefs();
    }
    IPCThreadState* ipc = IPCThreadState::self();
    if (ipc) ipc->decStrongHandle(mHandle);
}

void IPCThreadState::decStrongHandle(int32_t handle)
{
    LOG_REMOTEREFS("IPCThreadState::decStrongHandle(%d)\n", handle);
    mOut.writeInt32(BC_RELEASE);
    mOut.writeInt32(handle);
}
```

假设有 Client 进程将一个 Binder 代理对象封装成三个不同的 BpInterface 对象，并且这三个 BpInterface 对象都通过强指针来引用该 Binder 代理对象，因此，该 Binder 代理对象的强引用计数和弱引用计数就等于 3。由于一个 Binder 代理对象只有在创建时，才会增加相应的 Binder 引用对象的弱引用计数，并且只有在第一次被强指针引用时才会增加相应的 Binder 引用对象的强引用计数，因此Binder引用对象的强引用计数和弱引用计数均等于1，小于引用了它的 Binder 代理对象的强引用计数和弱引用计数，即一个 Binder 代理对象的引用计数与它所引用的 Binder 引用对象的引用计数是多对一的关系。这样做的好处是可以减少 Client 进程和Binder 驱动程序之间的交互，即可以减少它们之间的 BC_ACQUIRE、BC_INCREFS、BC_RELEASE和BC_DECREFS 协议来往。

<img src="android/framework/binder/binder_ref_count/resources/2.png" style="width:50%">