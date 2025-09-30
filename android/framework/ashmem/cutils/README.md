# 运行时库 cutils 的匿名共享内存访问接口

运行时库 cutils 的匿名共享内存访问接口实现在 ashmem-dev.c 文件中，这个文件提供了五个 C 接口来访问 Ashmem 驱动程序，它们分别是 ashmem_create_region、ashmem_pin_region、ashmem_unpin_region、ashmem_set_prot_region 和 ashmem_get_size_region。下面我们就分别分析这五个函数的实现。

## ashmem_create_region

这个函数很简单了，主要步骤如下:

1. 打开设备驱动文件。
2. 设置共享内存名称。
3. 设置贡献内存尺寸。

```c
/*
 * ashmem_create_region - creates a new ashmem region and returns the file
 * descriptor, or <0 on error
 *
 * `name' is an optional label to give the region (visible in /proc/pid/maps)
 * `size' is the size of the region, in page-aligned bytes
 */
int ashmem_create_region(const char *name, size_t size)
{
	int fd, ret;

	fd = open(ASHMEM_DEVICE, O_RDWR);
	if (fd < 0)
		return fd;

	if (name) {
		char buf[ASHMEM_NAME_LEN];

		strlcpy(buf, name, sizeof(buf));
		ret = ioctl(fd, ASHMEM_SET_NAME, buf);
		if (ret < 0)
			goto error;
	}

	ret = ioctl(fd, ASHMEM_SET_SIZE, size);
	if (ret < 0)
		goto error;

	return fd;

error:
	close(fd);
	return ret;
}
```

## ashmem_pin_region

函数 ashmem_pin_region 使用 IO 控制命令 ASHMEM_PIN 来请求 Ashmem 驱动程序锁定一小块匿名共享内存。其中，参数 fd 是前面打开设备文件/dev/ashmem 所得到的一个文件描述符；参数 offset 和 len 用来指定要锁定的内存块在其宿主匿名共享内存中的偏移地址和长度。

```c
int ashmem_pin_region(int fd, size_t offset, size_t len)
{
	struct ashmem_pin pin = { offset, len };
	return ioctl(fd, ASHMEM_PIN, &pin);
}
```

## ashmem_unpin_region

```c
int ashmem_unpin_region(int fd, size_t offset, size_t len)
{
	struct ashmem_pin pin = { offset, len };
	return ioctl(fd, ASHMEM_UNPIN, &pin);
}
```

## ashmem_set_prot_region

函数 ashmem_set_prot_region 使用 IO 控制命令 ASHMEM_SET_PROT_MASK 来请求 Ashmem 驱动程序修改一块匿名共享内存的访问保护位。

其中，参数 fd 是前面打开设备文件/dev/ashmem 所得到的一个文件描述符；参数 prot 指定要修改的访问保护位，它的取值为 PROT_EXEC、PROT_READ、PROT_WRITE 或其组合值。

```c
int ashmem_set_prot_region(int fd, int prot)
{
	return ioctl(fd, ASHMEM_SET_PROT_MASK, prot);
}
```

这个函数最后会调用到 ashmem 驱动中的函数 set_prot_mask。

```c
static int set_prot_mask(struct ashmem_area *asma, unsigned long prot)
{
	int ret = 0;

	mutex_lock(&ashmem_mutex);

	/* the user can only remove, not add, protection bits */
    // 不可以添加权限，只能移除权限
	if (unlikely((asma->prot_mask & prot) != prot)) {
		ret = -EINVAL;
		goto out;
	}

	/* does the application expect PROT_READ to imply PROT_EXEC? */
	if ((prot & PROT_READ) && (current->personality & READ_IMPLIES_EXEC))
		prot |= PROT_EXEC;

	asma->prot_mask = prot;

out:
	mutex_unlock(&ashmem_mutex);
	return ret;
}
```

## ashmem_get_size_region

函数 ashmem_get_size_region 使用 IO 控制命令 ASHMEM_GET_SIZE 来请求 Ashmem 驱动程序返回一块匿名共享内存的大小。其中，参数 fd 是前面打开设备文件/dev/ashmem 所得到的一个文件描述符。

```c
int ashmem_get_size_region(int fd)
{
  return ioctl(fd, ASHMEM_GET_SIZE, NULL);
}
```
