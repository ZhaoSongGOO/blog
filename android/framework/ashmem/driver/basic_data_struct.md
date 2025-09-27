# 基础数据类型

## ashmem_area

- name 是共享内存的名称。

- 成员变量 unpinned_list 用来描述一个解锁内存块列表。前面提到，一块匿名共享内存可以动态地划分为若干个小块，当这些小块的内存处于解锁状态时，它们就会被添加到所属匿名共享内存的解锁内存块列表中。解锁内存块列表中的内存块地址是互不相交的，并且按照地址值从大到小的顺序来排列。

- 成员变量 file 指向临时文件系统 tmpfs 中的一个文件，而成员变量 size 用来描述这个文件的大小。前面提到，匿名共享内存是基于 Linux 内核的临时文件系统 tmpfs 来实现的；因此，每一块匿名共享内存在临时文件系统 tmpfs 中都有一个对应的文件，这个文件的大小即为对应的匿名共享内存的大小。

- 成员变量 prot_mask 用来描述一块匿名共享内存的访问保护位。一块匿名共享内存的默认访问保护位被设置为 PROT_MASK。

```c
struct ashmem_area {
	char name[ASHMEM_FULL_NAME_LEN];/* optional name for /proc/pid/maps */
	struct list_head unpinned_list;	/* list of all ashmem areas */
	struct file *file;		/* the shmem-based backing file */
	size_t size;			/* size of the mapping, in bytes */
	unsigned long prot_mask;	/* allowed prot bits, as vm_flags */
};

#define PROT_MASK		(PROT_EXEC | PROT_READ | PROT_WRITE) // 可执行|可读|可写
```

## ashmem_range

- 这些处于解锁状态的小块内存都是从一块匿名共享内存中划分出来的，它们通过成员变量 unpinned 链入到宿主匿名共享内存的解锁内存块列表 unpinned_list 中。一块处于解锁状态的内存的宿主匿名共享内存是通过成员变量 asma 来描述的。

- 在 Ashmem 驱动程序中，每一块处于解锁状态的内存还会通过其成员变量 lru 链入到一个全局列表 ashmem_lru_list 中。全局列表 ashmem_lru_list 是一个最近最少使用列表(Least Recently Used)，它的定义如下所示。由于处于解锁状态的内存都是不再需要使用的，因此，当系统内存不足时，内存管理系统就会按照最近最少使用的原则来回收保存在全局列表 ashmem_lru_list 中的内存块。

- 成员变量 pgstart 和 pgend 分别用来描述一块处于解锁状态的内存的开始地址和结束地址，它们的单位是页。

- 最后，成员变量 purged 用来描述一块处于解锁状态的内存是否已经被回收。


```c
struct ashmem_range {
	struct list_head lru;		/* entry in LRU list */
	struct list_head unpinned;	/* entry in its area's unpinned list */
	struct ashmem_area *asma;	/* associated area */
	size_t pgstart;			/* starting page, inclusive */
	size_t pgend;			/* ending page, inclusive */
	unsigned int purged;		/* ASHMEM_NOT or ASHMEM_WAS_PURGED */
};
```

## ashmem_pin

结构体 ashmem_pin 是 Ashmem 驱动程序定义的 IO 控制命令 ASHMEM_PIN 和 ASHMEM_UNPIN 的参数，用来描述一小块即将被锁定或者解锁的内存。其中，成员变量 offset 表示这块即将被锁定或者解锁的内存在其宿主匿名共享内存块中的偏移值，而成员变量 len 表示要被锁定或者解锁的内存块的大小，它们都是以字节为单位，并且对齐到页面边界的。

```c
struct ashmem_pin {
	__u32 offset;	/* offset into region, in bytes, page-aligned */
	__u32 len;	/* length forward from offset, in bytes, page-aligned */
};
```