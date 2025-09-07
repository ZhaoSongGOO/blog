# binder 驱动


## 初始化函数

binder 本身就是一个 linux 驱动，开发和驱动开发是一样的，我们在 binder.c 中看到 device_initcall 的设置可以很容易的看到 binder 的初始化函数。

```c
static struct file_operations binder_fops = {
	.owner = THIS_MODULE,
	.poll = binder_poll,
	.unlocked_ioctl = binder_ioctl,
	.mmap = binder_mmap,
	.open = binder_open,
	.flush = binder_flush,
	.release = binder_release,
};

static struct miscdevice binder_miscdev = {
	.minor = MISC_DYNAMIC_MINOR,
	.name = "binder",
	.fops = &binder_fops
};

static int __init binder_init(void)
{
	int ret;

	binder_proc_dir_entry_root = proc_mkdir("binder", NULL);
	if (binder_proc_dir_entry_root)
		binder_proc_dir_entry_proc = proc_mkdir("proc", binder_proc_dir_entry_root);
	ret = misc_register(&binder_miscdev);
	if (binder_proc_dir_entry_root) {
		create_proc_read_entry("state", S_IRUGO, binder_proc_dir_entry_root, binder_read_proc_state, NULL);
		create_proc_read_entry("stats", S_IRUGO, binder_proc_dir_entry_root, binder_read_proc_stats, NULL);
		create_proc_read_entry("transactions", S_IRUGO, binder_proc_dir_entry_root, binder_read_proc_transactions, NULL);
		create_proc_read_entry("transaction_log", S_IRUGO, binder_proc_dir_entry_root, binder_read_proc_transaction_log, &binder_transaction_log);
		create_proc_read_entry("failed_transaction_log", S_IRUGO, binder_proc_dir_entry_root, binder_read_proc_transaction_log, &binder_transaction_log_failed);
	}
	return ret;
}
```

首先在 proc 目录下创建了一个新的目录叫 /proc/binder/proc 后续所有使用了 binder 的进程都是以进程号为名在这个目录下创建对应的文件，，通过它们就可以读取到各个进程的binder线程池、binder 实体对象、binder 引用对象以及内核缓冲区等信息。

然后注册了一个虚拟文件设备 /dev/binder, 并绑定这个虚拟设备文件的各种操作回调。

接下来又在 /proc/binder 目录下创建了五个文件 state、stats、transactions、transaction_log 和failed_transaction_log，通过这五个文件就可以读取到 binder 驱动程序的运行状况。例如，各个命令协议 (binderDriverCommandProtocol) 和返回协议 (binderDriverReturnProtocol) 的请求次数、日志记录信息，以及正在执行进程间通信过程的进程信息等。


## binder 设备打开

使用 open 打开 binder 设备文件 /dev/binder 会回调到 binder_open 函数。

这里面需要注意 current 是 linux 下面的一个宏，返回当前进程的 PCB，在 linux 下就是 `task_struct`。


```c
static int binder_open(struct inode *nodp, struct file *filp)
{
	// 初始化一个 binder_proc 结构体
    struct binder_proc *proc;

	if (binder_debug_mask & BINDER_DEBUG_OPEN_CLOSE)
		printk(KERN_INFO "binder_open: %d:%d\n", current->group_leader->pid, current->pid);

	proc = kzalloc(sizeof(*proc), GFP_KERNEL); // 类似于 malloc
	if (proc == NULL)
		return -ENOMEM;
	get_task_struct(current);
	proc->tsk = current; // 初始化 binder_proc 中的进程控制块
	INIT_LIST_HEAD(&proc->todo);
	init_waitqueue_head(&proc->wait);
	proc->default_priority = task_nice(current);
	mutex_lock(&binder_lock);
	binder_stats.obj_created[BINDER_STAT_PROC]++;
	hlist_add_head(&proc->proc_node, &binder_procs); // 把当前这个 binder_proc 添加到一个全局的 HList(binder_procs) 中 
	proc->pid = current->group_leader->pid;
	INIT_LIST_HEAD(&proc->delivered_death);
	filp->private_data = proc;  // 把这个 proc 保存，以便于后续文件操作使用。
	mutex_unlock(&binder_lock);

	if (binder_proc_dir_entry_proc) {
		char strbuf[11];
		snprintf(strbuf, sizeof(strbuf), "%u", proc->pid);
		remove_proc_entry(strbuf, binder_proc_dir_entry_proc);
		create_proc_read_entry(strbuf, S_IRUGO, binder_proc_dir_entry_proc, binder_read_proc_proc, proc);
	}

	return 0;
}
```

## binder 内存映射

在 open 设备文件后，我们需要 mmap 进行缓冲区分配，这个 mmap 操作会回调到 binder 的 binder_mmap 方法。

vm_area_struct 和 vm_struct 两者都是用来描述一段连续的虚拟内存空间, vm_area_struct 是内核中用来描述用户空间虚拟地址空间，vm_struct 是用来描述内核地址虚拟空间的。

```c
static int binder_mmap(struct file *filp, struct vm_area_struct *vma)
{
	int ret;
	struct vm_struct *area;
	struct binder_proc *proc = filp->private_data;
	const char *failure_string;
	struct binder_buffer *buffer;

	if ((vma->vm_end - vma->vm_start) > SZ_4M) // 判断用户地址空间范围大小，如果大于 4M 就截断成 4M。
		vma->vm_end = vma->vm_start + SZ_4M;

	if (binder_debug_mask & BINDER_DEBUG_OPEN_CLOSE)
		printk(KERN_INFO
			"binder_mmap: %d %lx-%lx (%ld K) vma %lx pagep %lx\n",
			proc->pid, vma->vm_start, vma->vm_end,
			(vma->vm_end - vma->vm_start) / SZ_1K, vma->vm_flags,
			(unsigned long)pgprot_val(vma->vm_page_prot));
    // 判断用户是不是设置了 写 标志，在 binder 映射的buffer中数据只可以由 binder 来写，对于用户来说的话，不可以写，只能读。
    // 所以如果设置了写，就直接报错。
	if (vma->vm_flags & FORBIDDEN_MMAP_FLAGS) {
		ret = -EPERM;
		failure_string = "bad vm_flags";
		goto err_bad_arg;
	}
	vma->vm_flags = (vma->vm_flags | VM_DONTCOPY) & ~VM_MAYWRITE;

    // 判断是不是已经分配过了，分配过了，那句直接返回。这个是不是可以放在最上面去做判断?
	if (proc->buffer) {
		ret = -EBUSY;
		failure_string = "already mapped";
		goto err_already_mapped;
	}

    // 分配 mmap 的地址，vma 是用户空间，area 对应的内核空间
	area = get_vm_area(vma->vm_end - vma->vm_start, VM_IOREMAP);
	if (area == NULL) {
		ret = -ENOMEM;
		failure_string = "get_vm_area";
		goto err_get_vm_area_failed;
	}
    // proc buffer 设置成内核空间的地址。
	proc->buffer = area->addr;
    // 用户空间与内核空间的地址偏移
	proc->user_buffer_offset = vma->vm_start - (uintptr_t)proc->buffer;

#ifdef CONFIG_CPU_CACHE_VIPT
	if (cache_is_vipt_aliasing()) {
		while (CACHE_COLOUR((vma->vm_start ^ (uint32_t)proc->buffer))) {
			printk(KERN_INFO "binder_mmap: %d %lx-%lx maps %p bad alignment\n", proc->pid, vma->vm_start, vma->vm_end, proc->buffer);
			vma->vm_start += PAGE_SIZE;
		}
	}
#endif
    // 分配物理页面结构体指针数组
	proc->pages = kzalloc(sizeof(proc->pages[0]) * ((vma->vm_end - vma->vm_start) / PAGE_SIZE), GFP_KERNEL);
	if (proc->pages == NULL) {
		ret = -ENOMEM;
		failure_string = "alloc page array";
		goto err_alloc_pages_failed;
	}
    // 初始化 buffer 的尺寸
	proc->buffer_size = vma->vm_end - vma->vm_start;

    // 初始化这个映射空间后面的操作回调，这里面包括一个 binder_vma_open 和 binder_vma_close。
	vma->vm_ops = &binder_vm_ops;
	vma->vm_private_data = proc;
    
    // 分配物理页面
	if (binder_update_page_range(proc, 1, proc->buffer, proc->buffer + PAGE_SIZE, vma)) {
		ret = -ENOMEM;
		failure_string = "alloc small buf";
		goto err_alloc_small_buf_failed;
	}
	buffer = proc->buffer;
	INIT_LIST_HEAD(&proc->buffers);
	list_add(&buffer->entry, &proc->buffers); // 把 binder_buffer 加入到 proc 的 buffers 列表中。
	buffer->free = 1;
    /*
    // 把 binder_buffer 插入到 proc 的空闲 buffer 红黑树中。
    这里你也可以发现，我们第一次分配的 4M 的缓冲区，这个会被视为一个 binder_buffer, 而且红黑树下也只会挂载这一个缓冲区。
    在后续使用中，类似于堆的拆分与重组，会从这个大的 buffer 中分配指定大小的 buffer 给用户。并在不使用的时候再进行合并。
    */
	binder_insert_free_buffer(proc, buffer);   
	proc->free_async_space = proc->buffer_size / 2; // 设置异步事务做大空间位 buffer 总尺寸的一半。
	barrier();
	proc->files = get_files_struct(current);
	proc->vma = vma;

	/*printk(KERN_INFO "binder_mmap: %d %lx-%lx maps %p\n", proc->pid, vma->vm_start, vma->vm_end, proc->buffer);*/
	return 0;

err_alloc_small_buf_failed:
	kfree(proc->pages);
	proc->pages = NULL;
err_alloc_pages_failed:
	vfree(proc->buffer);
	proc->buffer = NULL;
err_get_vm_area_failed:
err_already_mapped:
err_bad_arg:
	printk(KERN_ERR "binder_mmap: %d %lx-%lx %s failed %d\n", proc->pid, vma->vm_start, vma->vm_end, failure_string, ret);
	return ret;
}
```

## binder 缓冲区管理

### 分配内核缓冲区

在用户使用 binder 进行数据通信的时候，这些用户数据最终需要借助于 binder 提供的缓冲区来进行存储。

```c
static struct binder_buffer *binder_alloc_buf(struct binder_proc *proc,
	size_t data_size, size_t offsets_size, int is_async)
{   
    // 空闲缓冲区的红黑树根节点
	struct rb_node *n = proc->free_buffers.rb_node;
	struct binder_buffer *buffer;
	size_t buffer_size;
	struct rb_node *best_fit = NULL;
	void *has_page_addr;
	void *end_page_addr;
	size_t size;

	if (proc->vma == NULL) {
		printk(KERN_ERR "binder: %d: binder_alloc_buf, no vma\n",
		       proc->pid);
		return NULL;
	}

    // 获取要分配的 buffer 的总大小
    // ALIGN 的意思是 "把 data_size 对齐到指针大小的整数倍"
	size = ALIGN(data_size, sizeof(void *)) +
		ALIGN(offsets_size, sizeof(void *));

	if (size < data_size || size < offsets_size) {
		binder_user_error("binder: %d: got transaction with invalid "
			"size %zd-%zd\n", proc->pid, data_size, offsets_size);
		return NULL;
	}

    // 哦吼，异步事务已经没有空间了
	if (is_async &&
	    proc->free_async_space < size + sizeof(struct binder_buffer)) {
		if (binder_debug_mask & BINDER_DEBUG_BUFFER_ALLOC)
			printk(KERN_ERR "binder: %d: binder_alloc_buf size %zd f"
			       "ailed, no async space left\n", proc->pid, size);
		return NULL;
	}

	while (n) {
        // 获取该 rb_node 对应的 binder_buffer 对象
		buffer = rb_entry(n, struct binder_buffer, rb_node);
		BUG_ON(!buffer->free); // free tree 上不应该出现正在被使用的 buffe 对吧，所以报错。
        // 获取当前 binder_buff 的尺寸
		buffer_size = binder_buffer_size(proc, buffer);

        // 如果这个尺寸太大了，就去左子树，否则去右子树，但是暂时将结果先记录成 当前节点，为的是后面没有合适的就凑合用，目标是找到最接近尺寸且大于目标尺寸的节点。
		if (size < buffer_size) {
			best_fit = n;
			n = n->rb_left;
		} else if (size > buffer_size)
			n = n->rb_right;
		else {
			best_fit = n;
			break;
		}
	}
	if (best_fit == NULL) {
		printk(KERN_ERR "binder: %d: binder_alloc_buf size %zd failed, "
		       "no address space\n", proc->pid, size);
		return NULL;
	}

    // 这个说明。没有找到完全匹配的，所以使用 best_fit 节点来更新
	if (n == NULL) {
		buffer = rb_entry(best_fit, struct binder_buffer, rb_node);
		buffer_size = binder_buffer_size(proc, buffer);
	}
	if (binder_debug_mask & BINDER_DEBUG_BUFFER_ALLOC)
		printk(KERN_INFO "binder: %d: binder_alloc_buf size %zd got buff"
		       "er %p size %zd\n", proc->pid, size, buffer, buffer_size);

    // 空闲内核缓冲区buffer的结束地址所在的页面的起始地址
	has_page_addr =
		(void *)(((uintptr_t)buffer->data + buffer_size) & PAGE_MASK);
    // 如果分配的缓冲区比需要的大。
	if (n == NULL) {
        // 如果大的不多，即大小不超过一个 binder_buffer + 4 ，那就不切割了，全部分配给这次的 buffer。
		if (size + sizeof(struct binder_buffer) + 4 >= buffer_size)
			buffer_size = size; /* no room for other buffers */
		else
            // 否则，
			buffer_size = size + sizeof(struct binder_buffer);
	}
	end_page_addr =
		(void *)PAGE_ALIGN((uintptr_t)buffer->data + buffer_size);
	if (end_page_addr > has_page_addr)
		end_page_addr = has_page_addr;
	if (binder_update_page_range(proc, 1,
	    (void *)PAGE_ALIGN((uintptr_t)buffer->data), end_page_addr, NULL))
		return NULL;

	rb_erase(best_fit, &proc->free_buffers);
	buffer->free = 0;
    // 把这个新分配的 buffer 放置在 binder_proc 的在使用缓冲区红黑树上。
	binder_insert_allocated_buffer(proc, buffer);
	if (buffer_size != size) {
		struct binder_buffer *new_buffer = (void *)buffer->data + size;
		list_add(&new_buffer->entry, &buffer->entry);
		new_buffer->free = 1;
		binder_insert_free_buffer(proc, new_buffer);
	}
	if (binder_debug_mask & BINDER_DEBUG_BUFFER_ALLOC)
		printk(KERN_INFO "binder: %d: binder_alloc_buf size %zd got "
		       "%p\n", proc->pid, size, buffer);
	buffer->data_size = data_size;
	buffer->offsets_size = offsets_size;
	buffer->async_transaction = is_async;
	if (is_async) {
		proc->free_async_space -= size + sizeof(struct binder_buffer);
		if (binder_debug_mask & BINDER_DEBUG_BUFFER_ALLOC_ASYNC)
			printk(KERN_INFO "binder: %d: binder_alloc_buf size %zd "
			       "async free %zd\n", proc->pid, size,
			       proc->free_async_space);
	}

	return buffer;
}
```

### 释放内核缓冲区

当一个进程处理完成 Binder 驱动程序给它发送的返回协议 BR_TRANSACTION 或者 BR_REPLY 之后，它就会使用命令协议 BC_FREE_BUFFER 来通知 Binder 驱动程序释放相应的内核缓冲区，以免浪费系统内存。


```c
static void binder_free_buf(
	struct binder_proc *proc, struct binder_buffer *buffer)
{
	size_t size, buffer_size;

	buffer_size = binder_buffer_size(proc, buffer);

	size = ALIGN(buffer->data_size, sizeof(void *)) +
		ALIGN(buffer->offsets_size, sizeof(void *));
	if (binder_debug_mask & BINDER_DEBUG_BUFFER_ALLOC)
		printk(KERN_INFO "binder: %d: binder_free_buf %p size %zd buffer"
		       "_size %zd\n", proc->pid, buffer, size, buffer_size);

	BUG_ON(buffer->free);
	BUG_ON(size > buffer_size);
	BUG_ON(buffer->transaction != NULL);
	BUG_ON((void *)buffer < proc->buffer);
	BUG_ON((void *)buffer > proc->buffer + proc->buffer_size);

    // 判断是不是异步事务使用的缓冲区，如果是的话，需要给异步事务缓冲区尺寸恢复上去。
	if (buffer->async_transaction) {
		proc->free_async_space += size + sizeof(struct binder_buffer);
		if (binder_debug_mask & BINDER_DEBUG_BUFFER_ALLOC_ASYNC)
			printk(KERN_INFO "binder: %d: binder_free_buf size %zd "
			       "async free %zd\n", proc->pid, size,
			       proc->free_async_space);
	}
    // 后续做的事情就是释放对应的节点所占用的空间，从 allocated tree 中移除，并恢复到 free 红黑树中，同时合并前后紧邻的空闲的节点。
	binder_update_page_range(proc, 0,
		(void *)PAGE_ALIGN((uintptr_t)buffer->data),
		(void *)(((uintptr_t)buffer->data + buffer_size) & PAGE_MASK),
		NULL);
	rb_erase(&buffer->rb_node, &proc->allocated_buffers);
	buffer->free = 1;
	if (!list_is_last(&buffer->entry, &proc->buffers)) {
		struct binder_buffer *next = list_entry(buffer->entry.next,
						struct binder_buffer, entry);
		if (next->free) {
			rb_erase(&next->rb_node, &proc->free_buffers);
			binder_delete_free_buffer(proc, next);
		}
	}
	if (proc->buffers.next != &buffer->entry) {
		struct binder_buffer *prev = list_entry(buffer->entry.prev,
						struct binder_buffer, entry);
		if (prev->free) {
			binder_delete_free_buffer(proc, buffer);
			rb_erase(&prev->rb_node, &proc->free_buffers);
			buffer = prev;
		}
	}
	binder_insert_free_buffer(proc, buffer);
}
```

### 查询内核缓冲区

当一个进程使用完成一个内核缓冲区之后，它就会主动使用命令协议 BC_FREE_BUFFER 来通知 Binder 驱动程序释放内核缓冲区所对应的物理页面。然而，进程只知道要释放的内核缓冲区的用户空间地址，而 Binder 驱动程序需要知道用来描述该内核缓冲区的一个 binder_buffer 结构体，然后才可以释放它所占用的物理页面。因此，Binder 驱动程序提供了函数 binder_buffer_lookup 根据一个用户空间地址来查询一个内核缓冲区，它的实现如下所示。

首先用户空间地址减去之前的内核和用户空间的偏移量得到内核空间地址，这是 data 字段的地址，随后减去 data 到 binder_buffer 的偏移量得到 binder_buffer 的地址。

最后就是红黑树对比了，没啥好说的。

```c
static struct binder_buffer *binder_buffer_lookup(
	struct binder_proc *proc, void __user *user_ptr)
{
	struct rb_node *n = proc->allocated_buffers.rb_node;
	struct binder_buffer *buffer;
	struct binder_buffer *kern_ptr;

	kern_ptr = user_ptr - proc->user_buffer_offset
		- offsetof(struct binder_buffer, data);

	while (n) {
		buffer = rb_entry(n, struct binder_buffer, rb_node);
		BUG_ON(buffer->free);

		if (kern_ptr < buffer)
			n = n->rb_left;
		else if (kern_ptr > buffer)
			n = n->rb_right;
		else
			return buffer;
	}
	return NULL;
}
```





