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

## 设备文件打开

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
	memcpy(asma->name, ASHMEM_NAME_PREFIX, ASHMEM_NAME_PREFIX_LEN);
	asma->prot_mask = PROT_MASK;
	// 这个结构体保存在文件描述结构的 private data 中。
	file->private_data = asma;

	return 0;
}
```

## 设备文件内存映射

```c
static int ashmem_mmap(struct file *file, struct vm_area_struct *vma)
{
	struct ashmem_area *asma = file->private_data;
	int ret = 0;

	mutex_lock(&ashmem_mutex);

	/* user needs to SET_SIZE before mapping */
	if (unlikely(!asma->size)) {
		ret = -EINVAL;
		goto out;
	}

	/* requested protection bits must match our allowed protection mask */
	if (unlikely((vma->vm_flags & ~asma->prot_mask) & PROT_MASK)) {
		ret = -EPERM;
		goto out;
	}

	if (!asma->file) {
		char *name = ASHMEM_NAME_DEF;
		struct file *vmfile;

		if (asma->name[ASHMEM_NAME_PREFIX_LEN] != '\0')
			name = asma->name;

		/* ... and allocate the backing shmem file */
		vmfile = shmem_file_setup(name, asma->size, vma->vm_flags);
		if (unlikely(IS_ERR(vmfile))) {
			ret = PTR_ERR(vmfile);
			goto out;
		}
		asma->file = vmfile;
	}
	get_file(asma->file);

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



