# 匿名共享内存的原理

> [ashmem 下 fd, file, fops 解析](android/framework/ashmem/ref/fd_file_fops_ashmem_mmap.md)

当我们 open 一个文件的时候，我们会得到一个 fd，这个 fd 对应一个 `struct file` 的结构体，这个结构体中有一个成员 `f_pos` 注册了一系列 fd 操作的回调函数，对于 ashmem 来说，注册的就是 ashmem_fops 这个结构体绑定的回调函数。

我们在 A 进程基于 ashmem 创建了一个 fd1，在我们将这个 fd1 通过 binder 发送给 B 进程的时候，binder 驱动会在进程 B 中创建一个新的文件描述符 fd2，fd2 和 fd1 指向同一个 `struct file` 结构体，这就意味着他们指向了同一个 ashmem_area 数据。

那 binder 驱动是如何处理 fd 传递过程中的创建与绑定的呢？

Binder 驱动程序是在函数 binder_transaction 中处理进程间通信数据中类型为 BINDER_TYPE_FD 的 flat_binder_object 结构体的，如下所示。

首先从进程间通信数据中获得一个类型为 BINDER_TYPE_FD 的 flat_binder_object 结构体 fp，它的成员变量 handle 就是用来描述一个文件描述符的。

这个文件描述符只在源进程中有效。接着第 19 行调用函数 fget 来获得与文件描述符 fp-＞handle 对应的文件结构体 file。

调用函数 task_get_unused_fd_flags 在目标进程 target_proc 中获得一个未使用的文件描述符 target_fd，接着调用函数 task_fd_install 将它和文件结构体 file 关联起来。这样，源进程中的文件描述符 fp-＞handle 和目标进程中的文件描述符 target_fd 就指向了同一个文件结构体，即指向了同一块匿名共享内存。最后，将 flat_binder_object 结构体 fp 的成员变量 handle 的值设置为文件描述符 target_fd，以便可以将它返回给目标进程，即返回给 Client 组件。

Client 组件从 Binder 驱动程序中获得了 flat_binder_object 结构体 fp 之后，首先将它封装成一个 ParcelFileDescriptor 对象，然后再将它转换成一个 FileDescriptor 对象，最后就可以使用这个 FileDescriptor 对象来创建一个 MemoryFile 对象，即将 MemoryService 服务内部的匿名共享内存映射到 Client 组件所在的进程的地址空间，从而达到了在不同的进程中共享同一块匿名共享内存的目的。

```c
static void
binder_transaction(struct binder_proc *proc, struct binder_thread *thread,
	struct binder_transaction_data *tr, int reply)
{
    //...
    	for (; offp < off_end; offp++) {
		struct flat_binder_object *fp;
		//...
		fp = (struct flat_binder_object *)(t->buffer->data + *offp);
		switch (fp->type) {
		//...

		case BINDER_TYPE_FD: {
			int target_fd;
			struct file *file;

			//...
			file = fget(fp->handle);
			if (file == NULL) {
				b//...
				return_error = BR_FAILED_REPLY;
				goto err_fget_failed;
			}
			target_fd = task_get_unused_fd_flags(target_proc, O_CLOEXEC);
			if (target_fd < 0) {
				fput(file);
				return_error = BR_FAILED_REPLY;
				goto err_get_unused_fd_failed;
			}
			task_fd_install(target_proc, target_fd, file);
			//...
			fp->handle = target_fd;
		} break;

		default:
			binder_user_error("binder: %d:%d got transactio"
				"n with invalid object type, %lx\n",
				proc->pid, thread->pid, fp->type);
			return_error = BR_FAILED_REPLY;
			goto err_bad_object_type;
		}
	}
    //...
}
```

