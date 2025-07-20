# Android 专用驱动系统

Android系统是基于Linux内核开发的，但是为了更好地支持移动设备，它在Linux内核中增加了一些专用的驱动程序。这些专用的驱动程序形成了整个Android系统的坚实基础，它们被广泛地应用在Android系统的应用程序框架层中。正是因为这些专用的驱动程序有着如此重要的作用，我们就有必要重点掌握它们的实现原理。

## Logger 日志系统

Android 的日志系统基于内核中的 Logger 日志驱动程序实现，所有的日志保存在内核空间中，以环形缓冲区来保存日志，是一个有限的空间，当缓冲区满了后，新的日志会覆盖旧的日志。

<img src="android/framework/drivers/resources/log-driver-stack.png" style="width:40%">

### 日志分类

日志的类型分为四类：main、system、radio 和 events。类型为main的日志是应用程序级别的，而类型为system的日志是系统级别的。由于系统级日志要比应用程序级日志重要，因此，把它们分开来记录，可以避免系统级日志被应用程序级日志覆盖。类型为radio的日志是与无线设备相关的，它们的量很大，因此，把它们单独记录在一起，可以避免它们覆盖其他类型的日志。类型为events的日志是专门用来诊断系统问题的，应用程序开发者不应该使用此种类型的日志。

Android 提供了对应的 Java 和 c++ 接口来输出各种不同的日志，无论是Java日志写入接口还是C/C++日志写入接口，它们最终都是通过运行时库层的日志库liblog来往Logger日志驱动程序中写入日志的。此外，系统还提供了一个Logcat工具来读取和显示Logger日志驱动程序中的日志。

### Logger 日志格式

对于 main、system、radio 的日志格式如下：

- priority: 整数，代表优先级，一般有 VERBOSE、DEBUG、INFO、WARN、ERROR和FATAL六种。
- tag: 表示日志标签，是一个字符串。
- msg: 日志内容，也是一个字符串。

对于 event 类型的日志，格式如下：

- tag: 日志标签，整数。范围为 0~2147483648。
- msg: 二进制数据，户决定其内容。
    - 类型编码：分别用 1、2、3、4 来表示 int、long、string 和 list。
    - 数据：具体消息二进制数据

因为 event 事件的 tag 非常多，为了更友好的展示 event 日志的，Andorid 在 /system/etc/event-log-tags 文件中保存着可视化日志转化细节。

例如下面，含义如下：

- 2722： tag 数值，对应的日志名称为 battery_level
- (level|1|6),(voltage|1|1),(temperature|1|1)：代表数据内容格式
    - level: 第一个数据的名字为 level。
    - 1： 类型为整数
    - 6： 单位，它的取值范围是1～6，分别表示对象数量(number of objects)、字节数(Number of bytes)、毫秒数(Number of milliseconds)、分配额(Number of allocations)、标志(ID)和百分比(Percent)。

```txt
2722 battery_level (level|1|6),(voltage|1|1),(temperature|1|1)
```


### Linux Kernel Logger 日志驱动程序

这里交代一个背景，内核源码分析基于 `android-goldfish-2.6.29` 版本，Logger 日志驱动程序位于 LK 中, 是 Android 日志系统的底层能力。在后续的 5.x 版本内核中已经移除，需要额外注意。

#### 基础数据结构

1. logger_entry

代表一条日志，最大长度为 4K。

```c
struct logger_entry {
	__u16		len;	/* length of the payload */
	__u16		__pad;	/* no matter what, we get 2 bytes of padding */
	__s32		pid;	/* generating process's pid */
	__s32		tid;	/* generating process's tid */
	__s32		sec;	/* seconds since Epoch */
	__s32		nsec;	/* nanoseconds */
	char		msg[0];	/* the entry's payload */
};

#define LOGGER_LOG_RADIO	"log_radio"	/* radio-related messages */
#define LOGGER_LOG_EVENTS	"log_events"	/* system/hardware events */
#define LOGGER_LOG_MAIN		"log_main"	/* everything else */

#define LOGGER_ENTRY_MAX_LEN		(4*1024)
#define LOGGER_ENTRY_MAX_PAYLOAD	\
	(LOGGER_ENTRY_MAX_LEN - sizeof(struct logger_entry))
```

2. logger_log

代表一个日志缓冲区，每一种类型的日志都对应一个日志缓冲区。

buffer 指向日志缓冲区，wq 用来记录正在等待读取新日志记录的进程，readers 记录正在读取日志记录的进程。

head 代表当前日志缓冲区的头，w_off 代表下一条日志要写入的地方。

```c
/*
 * struct logger_log - represents a specific log, such as 'main' or 'radio'
 *
 * This structure lives from module insertion until module removal, so it does
 * not need additional reference counting. The structure is protected by the
 * mutex 'mutex'.
 */
struct logger_log {
	unsigned char *		buffer;	/* the ring buffer itself */
	struct miscdevice	misc;	/* misc device representing the log */
	wait_queue_head_t	wq;	/* wait queue for readers */
	struct list_head	readers; /* this log's readers */
	struct mutex		mutex;	/* mutex protecting buffer */
	size_t			w_off;	/* current write head offset */
	size_t			head;	/* new readers start here */
	size_t			size;	/* size of the log */
};
```

3. logger_reader

logger_reader 代表一个正在读取日志缓冲区日志记录的进程。成员变量r_off表示当前进程要读取的下一条日志记录在日志缓冲区中的位置。

```c
/*
 * struct logger_reader - a logging device open for reading
 *
 * This object lives from open to release, so we don't need additional
 * reference counting. The structure is protected by log->mutex.
 */
struct logger_reader {
	struct logger_log *	log;	/* associated log */
	struct list_head	list;	/* entry in logger_log's list */
	size_t			r_off;	/* current read head offset */
};
```

#### 日志驱动初始化流程

1. 定义 logger_log 静态变量

```c
#define DEFINE_LOGGER_DEVICE(VAR, NAME, SIZE) \
static unsigned char _buf_ ## VAR[SIZE]; \
static struct logger_log VAR = { \
	.buffer = _buf_ ## VAR, \
	.misc = { \
		.minor = MISC_DYNAMIC_MINOR, \
		.name = NAME, \
		.fops = &logger_fops, \
		.parent = NULL, \
	}, \
	.wq = __WAIT_QUEUE_HEAD_INITIALIZER(VAR .wq), \
	.readers = LIST_HEAD_INIT(VAR .readers), \
	.mutex = __MUTEX_INITIALIZER(VAR .mutex), \
	.w_off = 0, \
	.head = 0, \
	.size = SIZE, \
};

DEFINE_LOGGER_DEVICE(log_main, LOGGER_LOG_MAIN, 64*1024)
DEFINE_LOGGER_DEVICE(log_events, LOGGER_LOG_EVENTS, 256*1024)
DEFINE_LOGGER_DEVICE(log_radio, LOGGER_LOG_RADIO, 64*1024)
```

2. 驱动初始化

在 logger 驱动初始化函数中，直接以刚才初始化的三个静态变量来初始化设备文件。会在 /dev 目录下创建 main、events 和 radio 设备文件。

```c
static int __init init_log(struct logger_log *log)
{
	int ret;

	ret = misc_register(&log->misc);
	if (unlikely(ret)) {
		printk(KERN_ERR "logger: failed to register misc "
		       "device for log '%s'!\n", log->misc.name);
		return ret;
	}

	printk(KERN_INFO "logger: created %luK log '%s'\n",
	       (unsigned long) log->size >> 10, log->misc.name);

	return 0;
}

static int __init logger_init(void)
{
	int ret;

	ret = init_log(&log_main);
	if (unlikely(ret))
		goto out;

	ret = init_log(&log_events);
	if (unlikely(ret))
		goto out;

	ret = init_log(&log_radio);
	if (unlikely(ret))
		goto out;

out:
	return ret;
}
```

#### 打开日志设备文件

```c
static int logger_open(struct inode *inode, struct file *file)
{
	struct logger_log *log;
	int ret;
    // 关闭当前文件的随机读写权限，即日志只可以按序读取
	ret = nonseekable_open(inode, file);
	if (ret)
		return ret;
    // 依据设备号获取对应的 logger_log 对象。
	log = get_log_from_minor(MINOR(inode->i_rdev));
	if (!log)
		return -ENODEV;
    // 如果是读模式打开，就要创建 logger_reader 对象来保存读状态
	if (file->f_mode & FMODE_READ) {
		struct logger_reader *reader;

		reader = kmalloc(sizeof(struct logger_reader), GFP_KERNEL);
		if (!reader)
			return -ENOMEM;

		reader->log = log;
		INIT_LIST_HEAD(&reader->list);

		mutex_lock(&log->mutex);
		reader->r_off = log->head;
		list_add_tail(&reader->list, &log->readers);
		mutex_unlock(&log->mutex);

		file->private_data = reader;
	} else {
        // 写模式就简单了，直接返回 log 对象就行了
		file->private_data = log;
    }

	return 0;
}
```

#### 读写日志设备文件

1. 读日志

```c
/* * 行为说明：
 *
 *   - 支持 O_NONBLOCK（非阻塞模式）
 *   - 如果当前没有日志可读，则阻塞，直到有新日志写入
 *   - 每次原子性地读取**恰好一条**日志记录
 *
 * 最佳读取缓冲区大小为 LOGGER_ENTRY_MAX_LEN。如果读取缓冲区不足以容纳下一条日志记录，则会将 errno 设为 EINVAL。
 */
static ssize_t logger_read(struct file *file, char __user *buf,
			   size_t count, loff_t *pos)
{
	struct logger_reader *reader = file->private_data;
	struct logger_log *log = reader->log;
	ssize_t ret;
	DEFINE_WAIT(wait);

start:
    // while 循环用来检测是否有日志可以读取
	while (1) {
		prepare_to_wait(&log->wq, &wait, TASK_INTERRUPTIBLE); // 加入等待队列

		mutex_lock(&log->mutex);
		ret = (log->w_off == reader->r_off); // 是否有日志
		mutex_unlock(&log->mutex);
		if (!ret)
			break;

		if (file->f_flags & O_NONBLOCK) { // 如果是非阻塞模式，那就返回吧
			ret = -EAGAIN;
			break;
		}

		if (signal_pending(current)) { // 请求进程进入阻塞态的标准前置流程，如果该进程正在处理信号，那不可以进入阻塞态。
			ret = -EINTR;
			break;
		}

		schedule(); // 进入阻塞态
	}

	finish_wait(&log->wq, &wait); // 从等待队列中移除
	if (ret) // 如果有返回值，就返回，这里一般是非阻塞模式或者申请进入阻塞态失败。
		return ret;

	mutex_lock(&log->mutex);
    // 加锁后，再次判断
	/* is there still something to read or did we race? */
	if (unlikely(log->w_off == reader->r_off)) {
		mutex_unlock(&log->mutex);
		goto start;
	}
    // 获取日志长度，如果日志长度超过缓冲区，就直接返回，不读了，并设置错误码
	/* get the size of the next entry */
	ret = get_entry_len(log, reader->r_off);
	if (count < ret) {
		ret = -EINVAL;
		goto out;
	}

	/* get exactly one entry from the log */
	ret = do_read_log_to_user(log, reader, buf, ret);

out:
	mutex_unlock(&log->mutex);

	return ret;
}
```

这里在获取下一个缓冲区长度的时候，因为缓冲区是循环使用的，所以有如下的逻辑, 这里是因为 logger_log 中的每一条日志都是使用的 logger_entry 来进行保存的，logger_entry 前两个字节是 len，记录到是日志负载的长度。

因为是循环使用，len 可能会被一分为二，第一个字节放到尾端，一个防御首端，所以此时就需要进行分类考虑了。

```c
static __u32 get_entry_len(struct logger_log *log, size_t off)
{
	__u16 val;

	switch (log->size - off) {
	case 1:
		memcpy(&val, log->buffer + off, 1);
		memcpy(((char *) &val) + 1, log->buffer, 1);
		break;
	default:
		memcpy(&val, log->buffer + off, 2);
	}

	return sizeof(struct logger_entry) + val;
}
```

2. 写日志

```c
/*
 * logger_aio_write - our write method, implementing support for write(),
 * writev(), and aio_write(). Writes are our fast path, and we try to optimize
 * them above all else.
 */
ssize_t logger_aio_write(struct kiocb *iocb, const struct iovec *iov,
			 unsigned long nr_segs, loff_t ppos)
{
	struct logger_log *log = file_get_log(iocb->ki_filp);
	size_t orig = log->w_off;
	struct logger_entry header;
	struct timespec now;
	ssize_t ret = 0;

	now = current_kernel_time();

	header.pid = current->tgid;
	header.tid = current->pid;
	header.sec = now.tv_sec;
	header.nsec = now.tv_nsec;
	header.len = min_t(size_t, iocb->ki_left, LOGGER_ENTRY_MAX_PAYLOAD);

	/* null writes succeed, return zero */
	if (unlikely(!header.len))
		return 0;

	mutex_lock(&log->mutex);

	/*
	 * Fix up any readers, pulling them forward to the first readable
	 * entry after (what will be) the new write offset. We do this now
	 * because if we partially fail, we can end up with clobbered log
	 * entries that encroach on readable buffer.
	 */
    // 这个函数会判断当前日志写入后会不会因为满了覆盖旧数据。如果覆盖了，就把现在正在读数据的进程的下一次读取日志偏移挪到下一个，以避免读取的内容错乱。
	fix_up_readers(log, sizeof(struct logger_entry) + header.len);

    // 将 logger_entry 写入到 buffer 中。
	do_write_log(log, &header, sizeof(struct logger_entry));

    // 将日志内容写入到 buffer 中，更准确的是之前 entry 的payload 中。
	while (nr_segs-- > 0) {
		size_t len;
		ssize_t nr;

		/* figure out how much of this vector we can keep */
		len = min_t(size_t, iov->iov_len, header.len - ret);

		/* write out this segment's payload */
		nr = do_write_log_from_user(log, iov->iov_base, len);
		if (unlikely(nr < 0)) {
			log->w_off = orig;
			mutex_unlock(&log->mutex);
			return nr;
		}

		iov++;
		ret += nr;
	}

	mutex_unlock(&log->mutex);

	/* wake up any blocked readers */
	wake_up_interruptible(&log->wq);

	return ret;
}
```

#### 运行时日志库

AOSP 基于对内核的 logger 驱动包装，提供了一个运行时的日志库 liblog, 位于 `system/logging/liblog`。

<img src="android/framework/drivers/resources/liblog.png" style="width:60%">

根据写入的日志记录的类型不同，这些函数可以划分为三个类别。其中，函数 __android_log_assert 、 __android_log_vprint 和 __android_log_print 用来写入类型为 main 的日志记录；函数 __android_log_btwrite 和 __android_log_bwrite 用来写入类型为 events 的日志记录；函数 __android_log_buf_print 可以写入任意一种类型的日志记录。特别地，在函数 __android_log_write 和 __android_log_buf_write 中，如果要写入的日志记录的标签以“RIL”开头或者等于“HTC_RIL”​、​“AT”​、​“GSM”​、​“STK”​、​“CDMA”​、​“PHONE”或“SMS”​，那么它们就会被认为是radio类型的日志记录。

#### C/C++ 日志写入接口

C/C++ 中提供了一些定义好的宏来进行日志写入。

1. main 日志

LOGV、LOGD、LOGI、LOGW和LOGE，这五个宏是用来写入类型为main的日志记录的，它们写入的日志记录的优先级分别为VERBOSE、DEBUG、INFO、WARN和ERROR。其中，宏LOGV只有在宏LOG_NDEBUG定义为0时，即在程序的调试版本中，才是有效的；否则，它只是一个空定义。

2. system 日志

SLOGV、SLOGD、SLOGI、SLOGW和SLOGE，记录的优先级分别为VERBOSE、DEBUG、INFO、WARN和ERROR。其中，宏SLOGV只有在宏LOG_NDEBUG定义为0时，即在程序的调试版本中，才是有效的；否则，它只是一个空定义。

3. event 日志

LOG_EVENT_INT、LOG_EVENT_LONG和LOG_EVENT_STRING，这三个宏是用来写入类型为events的日志记录的。第6行到第9行首先定义了四个枚举值，它们分别用来代表一个整数(int)、长整数(long)、字符串(string)和列表(list)。前面提到，类型为events的日志记录的内容是由一系列值组成的，这些值是具有类型的，分别对应于EVENT_TYPE_INT、EVENT_TYPE_LONG、EVENT_TYPE_STRING和EVENT_TYPE_LIST四种类型。


#### Java 日志写入接口

Android系统在应用程序框架层中定义了三个Java日志写入接口，它们分别是android.util.Log、android.util.Slog和android.util.EventLog，写入的日志记录类型分别为main、system和events。这三个Java日志写入接口是通过JNI方法来调用日志库liblog提供的函数来实现日志记录的写入功能的。

#### Logcat 工具分析




