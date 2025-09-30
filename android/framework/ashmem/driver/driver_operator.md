# 匿名共享内存设备的操作

## 设备文件初始化

```c
static int __init ashmem_init(void)
{
	int ret;

    // 注册一个 slab 缓冲区分配器，用于 ashmem_area 的分配

	ashmem_area_cachep = kmem_cache_create("ashmem_area_cache",
					  sizeof(struct ashmem_area),
					  0, 0, NULL);
	if (unlikely(!ashmem_area_cachep)) {
		printk(KERN_ERR "ashmem: failed to create slab cache\n");
		return -ENOMEM;
	}
    // 注册第二个 slab 缓冲区分配器。用于 ashmem_range 结构体的分配
	ashmem_range_cachep = kmem_cache_create("ashmem_range_cache",
					  sizeof(struct ashmem_range),
					  0, 0, NULL);
	if (unlikely(!ashmem_range_cachep)) {
		printk(KERN_ERR "ashmem: failed to create slab cache\n");
		return -ENOMEM;
	}

    // 注册一个匿名共享内存设备之外，这个操作后会在 /dev 目录下出现一个 内存设备 ashmem
	ret = misc_register(&ashmem_misc);
	if (unlikely(ret)) {
		printk(KERN_ERR "ashmem: failed to register misc device!\n");
		return ret;
	}
    // 调用函数 register_shrinker 向内存管理系统注册一个内存回收函数 ashmem_shrinker。
    // 当系统内存不足时，内存管理系统就会通过一个页框回收算法(Page Frame Reclaiming Algorithm，PFRA)来回收内存，
    // 这时候所有调用函数 register_shrinker 注册的内存回收函数都会被调用，以便它们可以向系统贡献空闲或者相对空闲的内存。
	register_shrinker(&ashmem_shrinker);

	printk(KERN_INFO "ashmem: initialized\n");

	return 0;
}
/*
从 file_operations 结构体 ashmem_fops 的定义可以知道，设备文件/dev/ashmem 对应的文件打开、关闭、内存映射、IO 控制函数分别为 ashmem_open、ashmem_release、ashmem_mmap 和 ashmem_ioctl。
由于匿名共享内存的访问方式是直接地址访问，即先映射进程的地址空间，然后再通过虚拟地址来直接访问，因此，设备文件/dev/ashmem 就没有对应的读写函数。
*/
static struct file_operations ashmem_fops = {
	.owner = THIS_MODULE,
	.open = ashmem_open,
	.release = ashmem_release,
	.mmap = ashmem_mmap,
	.unlocked_ioctl = ashmem_ioctl,
	.compat_ioctl = ashmem_ioctl,
};

static struct miscdevice ashmem_misc = {
	.minor = MISC_DYNAMIC_MINOR,
	.name = "ashmem",
	.fops = &ashmem_fops,
};
```

## 设备文件打开以及初始化设置

```c
static int ashmem_open(struct inode *inode, struct file *file)
{
	struct ashmem_area *asma;
	int ret;
	ret = nonseekable_open(inode, file);
	if (unlikely(ret))
		return ret;
	
	// 分配一个 ashmem_area 结构体
	asma = kmem_cache_zalloc(ashmem_area_cachep, GFP_KERNEL);
	if (unlikely(!asma))
		return -ENOMEM;

	INIT_LIST_HEAD(&asma->unpinned_list);
	// 初始化的名字是 ASHMEM_NAME_PREFIX，就是  `#define ASHMEM_NAME_PREFIX "dev/ashmem/"`
	memcpy(asma->name, ASHMEM_NAME_PREFIX, ASHMEM_NAME_PREFIX_LEN);
	asma->prot_mask = PROT_MASK;
	// 这个结构体保存在文件描述结构的 private data 中。
	file->private_data = asma;

	return 0;
}
```

使用 `ASHMEM_SET_NAME` 设置名字，这里其实就是设置 ashmem_area 的名字

```c
static long ashmem_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
	struct ashmem_area *asma = file->private_data;
	long ret = -ENOTTY;

	switch (cmd) {
	case ASHMEM_SET_NAME:
		ret = set_name(asma, (void __user *) arg);
		break;
	//...
	}
}
```

`set_name` 的内容如下，首先会判断 `asma->file` 是不是存在，如果存在就意味着已经为 ashmem 分配了临时文件，分配了临时文件后就不允许更改名字了，直接返回。

如果没有分配临时文件，那就会以 `dev/ashmem/` 为前缀加上用户指定的名字设置 ashmem 的名称。

```c
static int set_name(struct ashmem_area *asma, void __user *name)
{
	int ret = 0;

	mutex_lock(&ashmem_mutex);

	/* cannot change an existing mapping's name */
	if (unlikely(asma->file)) {
		ret = -EINVAL;
		goto out;
	}

	if (unlikely(copy_from_user(asma->name + ASHMEM_NAME_PREFIX_LEN,
				    name, ASHMEM_NAME_LEN)))
		ret = -EFAULT;
	asma->name[ASHMEM_FULL_NAME_LEN-1] = '\0';

out:
	mutex_unlock(&ashmem_mutex);

	return ret;
}
```

同样的，可以使用 `ioctl` 来设置匿名内存的大小。同样的，如果已经创建了，那就不允许再修改了。

```c
static long ashmem_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
	struct ashmem_area *asma = file->private_data;
	long ret = -ENOTTY;

	switch (cmd) {
	//...
	case ASHMEM_SET_SIZE:
		ret = -EINVAL;
		if (!asma->file) {
			ret = 0;
			asma->size = (size_t) arg;
		}
		break;
		//..
	}
}
```

## 设备文件内存映射

当应用程序调用函数 mmap 将前面打开的设备文件 /dev/ashmem 映射到进程的地址空间时，Ashmem 驱动程序中的函数 ashmem_mmap 就会被执行，用来为前面创建的一块匿名共享内存创建一个临时文件。

```c
static int ashmem_mmap(struct file *file, struct vm_area_struct *vma)
{
	struct ashmem_area *asma = file->private_data;
	int ret = 0;

	mutex_lock(&ashmem_mutex);

	/* user needs to SET_SIZE before mapping */
	// 检查尺寸是不是设置了，没有设置尺寸那就返回
	if (unlikely(!asma->size)) {
		ret = -EINVAL;
		goto out;
	}

	/* requested protection bits must match our allowed protection mask */
	if (unlikely((vma->vm_flags & ~asma->prot_mask) & PROT_MASK)) {
		ret = -EPERM;
		goto out;
	}
	// 如果还没有创建 临时文件，那需要创建一下临时文件
	if (!asma->file) {
		char *name = ASHMEM_NAME_DEF; // "dev/ashmem"
		struct file *vmfile;

		if (asma->name[ASHMEM_NAME_PREFIX_LEN] != '\0')
			name = asma->name;

		/* ... and allocate the backing shmem file */
		// 在临时文件系统中创建一个文件
		vmfile = shmem_file_setup(name, asma->size, vma->vm_flags);
		if (unlikely(IS_ERR(vmfile))) {
			ret = PTR_ERR(vmfile);
			goto out;
		}
		asma->file = vmfile;
	}
	// #define get_file(x)	atomic_long_inc(&(x)->f_count)
	// 增加引用计数
	get_file(asma->file);
	// 如果这个虚拟内存允许多进程共享
	// 调用函数 shmem_set_file 设置它的映射文件，以及它的内存操作方法表。
	if (vma->vm_flags & VM_SHARED)
		shmem_set_file(vma, asma->file);
	else {
		if (vma->vm_file)
			fput(vma->vm_file);
		vma->vm_file = asma->file;
	}
	vma->vm_flags |= VM_CAN_NONLINEAR;

out:
	mutex_unlock(&ashmem_mutex);
	return ret;
}
```

`sheme_set_file` 的内容如下。

将虚拟内存 vma 的映射文件设置为前面为匿名共享内存 asma 所创建的临时文件，接着将虚拟内存 vma 的内存操作方法表设置为 shmem_vm_ops。shmem_vm_ops是一个类型为vm_operations_struct的结构体，它的成员变量fault指向了函数shmem_fault。

开始的时候，虚拟内存vma是没有映射物理页面的；因此，当它第一次被访问时，就会发生缺页异常(Page Fault)，这时候内核就会调用它的内存操作方法表中的函数shmem_fault给它映射物理页面。

函数shmem_fault首先会在页面缓冲区中检查是否存在与缺页的虚拟地址对应的物理页面。如果存在，就直接将它们映射到缺页的虚拟地址；否则，再去页面换出设备中检查是否存在与缺页的虚拟地址对应的换出页面。

如果存在，就先把它们添加到页面缓冲区中，然后再映射到缺页的虚拟地址；否则，就需要为缺页的虚拟地址分配新的物理页面，并且从虚拟内存vma的映射文件vm_file中读入相应的内容来初始化这些新分配的物理页面，最后将这些物理页面加入到页面缓冲区中去。

通过这种方式，我们就可以将一个物理页面映射到两个不同进程的虚拟地址空间，从而通过内存映射机制来实现共享内存的功能。

> [这段逻辑的解释](android/framework/ashmem/ref/vma_fault_theory.md)
> [临时文件到底是什么?](android/framework/ashmem/ref/tmpfs_in_ashmem.md)

```c
void shmem_set_file(struct vm_area_struct *vma, struct file *file)
{
	if (vma->vm_file)
		fput(vma->vm_file);
	vma->vm_file = file;
	vma->vm_ops = &shmem_vm_ops;
}
```

## 匿名共享内存的锁定和解锁过程

> 初始状态下，所有的内存都是 pinned 状态。

匿名共享内存是以分块的形式来管理的，应用程序可以对这些小块内存执行锁定或者解锁操作，其中，处于解锁状态的内存是可以被内存管理系统回收的。

一块匿名共享内存在创建时是处于锁定状态的，接下来，应用程序可以根据需要把它划分成若干个小块来使用。当其中的某些小块内存不再使用时，应用程序就可以对它们执行解锁操作，从而可以在内存紧张时为内存管理系统贡献内存。处于解锁状态的内存如果还没有被回收，那么应用程序还可以对它们执行锁定操作，从而阻止它们被内存管理系统回收。

用户可以通过 `ASHMEM_PIN` 和 `ASHMEM_UNPIN` 两个操作数来锁定和解锁一块匿名共享内存。

```c
static long ashmem_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
	struct ashmem_area *asma = file->private_data;
	long ret = -ENOTTY;

	switch (cmd) {
	//...
	case ASHMEM_PIN:
	case ASHMEM_UNPIN:
	case ASHMEM_GET_PIN_STATUS:
		ret = ashmem_pin_unpin(asma, cmd, (void __user *) arg);
		break;
	//...
	}
}
```

具体的处理函数如下,

```c
static int ashmem_pin_unpin(struct ashmem_area *asma, unsigned long cmd,
			    void __user *p)
{
	struct ashmem_pin pin;
	size_t pgstart, pgend;
	int ret = -EINVAL;
	// 如果还没有 mmap，那就报错并返回
	if (unlikely(!asma->file))
		return -EINVAL;
	// 把用户的输入参数拷贝到 pin 中。
	if (unlikely(copy_from_user(&pin, p, sizeof(pin))))
		return -EFAULT;

	/* per custom, you can pass zero for len to mean "everything onward" */
	// 如果尺寸是0，那内部就设置尺寸为从偏移量到整体尺寸的区间长度。
	if (!pin.len)
		pin.len = PAGE_ALIGN(asma->size) - pin.offset;
	// 是否对齐内存边界。本质上就是看是不是页大小的整数倍
	if (unlikely((pin.offset | pin.len) & ~PAGE_MASK))
		return -EINVAL;

	if (unlikely(((__u32) -1) - pin.offset < pin.len))
		return -EINVAL;
	// 是不是超出了 ashmem 分配的内存大小
	if (unlikely(PAGE_ALIGN(asma->size) < pin.offset + pin.len))
		return -EINVAL;
	// 计算要锁定或者解锁的内存块的开始地址和结束地址，并且保存在变量pgstart和pgend中。它们是以页为单位的，
	// 并且是一个相对地址，即相对匿名共享内存asma的起始地址。
	pgstart = pin.offset / PAGE_SIZE;
	pgend = pgstart + (pin.len / PAGE_SIZE) - 1;

	mutex_lock(&ashmem_mutex);

	switch (cmd) {
	case ASHMEM_PIN:
		// 加锁内存
		ret = ashmem_pin(asma, pgstart, pgend);
		break;
	case ASHMEM_UNPIN:
		// 解锁内存
		ret = ashmem_unpin(asma, pgstart, pgend);
		break;
	case ASHMEM_GET_PIN_STATUS:
		ret = ashmem_get_pin_status(asma, pgstart, pgend);
		break;
	}

	mutex_unlock(&ashmem_mutex);

	return ret;
}
```

首先来看内存解锁的过程。前面提到，一块匿名共享内存的所有解锁内存块都是按照地址值从大到小的顺序保存在其解锁内存块列表unpinned_list中的，并且它们是互不相交的。因此，函数ashmem_unpin在解锁一个内存块时，首先检查这个内存块是否与那些处于解锁状态的内存块相交。如果相交，就要对它们进行合并，然后在目标匿名共享内存的解锁内存块列表unpinned_list中找到一个合适的位置来保存合并后得到的内存块。

<img src="android/framework/ashmem/resources/2.png" style="width:70%">

```c
static int ashmem_unpin(struct ashmem_area *asma, size_t pgstart, size_t pgend)
{
	struct ashmem_range *range, *next;
	unsigned int purged = ASHMEM_NOT_PURGED;

	/*
	循环在目标匿名共享内存asma的解锁内存块列表unpinned_list中遍历每一块处于解锁状态的内存。
	如果发现一个已解锁内存块range与即将要解锁的内存块[pgstart，pgend]相交，那么就需要对它们执行合并操作，
	即调整参数pgstart和pgend的值，使得已解锁内存块range包含在它里面。
	*/
restart:
	list_for_each_entry_safe(range, next, &asma->unpinned_list, unpinned) {
		/* short circuit: this is our insertion point */
		if (range_before_page(range, pgstart))
			break;

		/*
		 * The user can ask us to unpin pages that are already entirely
		 * or partially pinned. We handle those two cases here.
		 */
		if (page_range_subsumed_by_range(range, pgstart, pgend))
			return 0;
		if (page_range_in_range(range, pgstart, pgend)) {
			pgstart = min_t(size_t, range->pgstart, pgstart),
			pgend = max_t(size_t, range->pgend, pgend);
			purged |= range->purged;
			range_del(range);
			goto restart;
		}
	}

	return range_alloc(asma, range, purged, pgstart, pgend);
}
```

然后看内存锁定过程，`ashmem_pin`，锁定的本质就是从 unpinned_list 中找到对应大小的 range，并将其从 unpinned_list 中删除，最后调整 ashmem_lru_list 尺寸大小即可。

锁定的区间和解锁类似，需要将两个区间进行 diff，并调整对应的范围。

```c
static int ashmem_pin(struct ashmem_area *asma, size_t pgstart, size_t pgend)
{
	struct ashmem_range *range, *next;
	int ret = ASHMEM_NOT_PURGED;

	list_for_each_entry_safe(range, next, &asma->unpinned_list, unpinned) {
		/* moved past last applicable page; we can short circuit */
		if (range_before_page(range, pgstart))
			break;

		/*
		 * The user can ask us to pin pages that span multiple ranges,
		 * or to pin pages that aren't even unpinned, so this is messy.
		 *
		 * Four cases:
		 * 1. The requested range subsumes an existing range, so we
		 *    just remove the entire matching range.
		 * 2. The requested range overlaps the start of an existing
		 *    range, so we just update that range.
		 * 3. The requested range overlaps the end of an existing
		 *    range, so we just update that range.
		 * 4. The requested range punches a hole in an existing range,
		 *    so we have to update one side of the range and then
		 *    create a new range for the other side.
		 */
		if (page_range_in_range(range, pgstart, pgend)) {
			ret |= range->purged;

			/* Case #1: Easy. Just nuke the whole thing. */
			if (page_range_subsumes_range(range, pgstart, pgend)) {
				range_del(range);
				continue;
			}

			/* Case #2: We overlap from the start, so adjust it */
			if (range->pgstart >= pgstart) {
				range_shrink(range, pgend + 1, range->pgend);
				continue;
			}

			/* Case #3: We overlap from the rear, so adjust it */
			if (range->pgend <= pgend) {
				range_shrink(range, range->pgstart, pgstart-1);
				continue;
			}

			/*
			 * Case #4: We eat a chunk out of the middle. A bit
			 * more complicated, we allocate a new range for the
			 * second half and adjust the first chunk's endpoint.
			 */
			range_alloc(asma, range, range->purged,
				    pgend + 1, range->pgend);
			range_shrink(range, range->pgstart, pgstart - 1);
			break;
		}
	}

	return ret;
}
```

## 匿名共享内存块的回收过程

Ashmem驱动程序在启动时，向内存管理系统注册了一个内存回收函数ashmem_shrink。当系统内存不足时，函数ashmem_shrink就会被调用来回收那些处于解锁状态的匿名共享内存。

数nr_to_scan表示内存管理系统希望回收的内存页数。如果它的值等于0，那么就表示内存管理系统并不是通知函数ashmem_shrink去执行回收匿名共享内存的操作，而是查询Ashmem驱动程序目前有多少匿名共享内存页可以被回收。

因此，将全局变量lru_count的值返回给调用者。如果参数nr_to_scan的值大于0，那么接下来的for循环就遍历全局列表ashmem_lru_list中的解锁内存块，并且逐一地调用函数vmtruncate_range来回收它们所占用的物理页面，直到回收的物理页面数达到nr_to_scan，或者全局列表ashmem_lru_list中已经没有内存可回收为止。

```c
/*
这个函数是 `ashmem` 驱动向 Linux 内核内存管理子系统（MM）注册的一个回调函数。当系统内存不足时，内核的页面扫描代码（`vmscan.c`）会调用这个函数，命令 `ashmem` “吐出”一些内存。

这个函数有两种工作模式。如果内核给的 `nr_to_scan` 大于 0，意思是“请帮我释放至少这么多页内存”。如果给的是 0，意思是“请告诉我你现在有多少页内存是可以被释放的”，这用于内核做统计和决策。

`gfp_mask` (Get Free Pages mask) 描述了触发这次内存回收的分配请求的上下文和约束（比如，是否允许睡眠等待、是否可以执行 I/O 等）。`ashmem_shrink` 函数需要检查这个掩码，以避免在不合适的上下文（比如不能睡眠时）尝试获取可能会导致睡眠的锁，从而引发死锁。

如果成功释放了内存，函数需要返回还剩下多少可释放的页面。返回 -1 是一个特殊的信号，告诉内核：“我很想帮你，但根据你给的 `gfp_mask`，我现在如果去加锁做事，可能会死锁，所以我这次放弃了。

这是最核心的实现细节。`ashmem` 并没有一个真正的、按访问时间排序的 LRU 列表。它用了一个巧妙的近似算法：它维护了一个“未被钉住区域 (`ashmem_range`)”的全局 LRU 列表。当一个区域被 `unpin` 时，它会被放到这个列表的末尾。因此，列表头部的区域就是最久以前被 `unpin` 的。`ashmem_shrink` 函数就从这个列表的头部开始，一个一个地拿出这些最老的 `unpinned` 区块，释放它们对应的物理内存，直到满足内核要求的 `nr_to_scan` 数量为止。
 * ashmem_shrink - our cache shrinker, called from mm/vmscan.c :: shrink_slab
 *
 * 'nr_to_scan' is the number of objects (pages) to prune, or 0 to query how
 * many objects (pages) we have in total.
 *
 * 'gfp_mask' is the mask of the allocation that got us into this mess.
 *
 * Return value is the number of objects (pages) remaining, or -1 if we cannot
 * proceed without risk of deadlock (due to gfp_mask).
 *
 * We approximate LRU via least-recently-unpinned, jettisoning unpinned partial
 * chunks of ashmem regions LRU-wise one-at-a-time until we hit 'nr_to_scan'
 * pages freed.
 */
static int ashmem_shrink(int nr_to_scan, gfp_t gfp_mask)
{
	struct ashmem_range *range, *next;

	/* We might recurse into filesystem code, so bail out if necessary */
	if (nr_to_scan && !(gfp_mask & __GFP_FS))
		return -1;
	if (!nr_to_scan)
		return lru_count;

	mutex_lock(&ashmem_mutex);
	list_for_each_entry_safe(range, next, &ashmem_lru_list, lru) {
		struct inode *inode = range->asma->file->f_dentry->d_inode;
		loff_t start = range->pgstart * PAGE_SIZE;
		loff_t end = (range->pgend + 1) * PAGE_SIZE - 1;

		vmtruncate_range(inode, start, end);
		range->purged = ASHMEM_WAS_PURGED;
		lru_del(range);

		nr_to_scan -= range_size(range);
		if (nr_to_scan <= 0)
			break;
	}
	mutex_unlock(&ashmem_mutex);

	return lru_count;
}
```





