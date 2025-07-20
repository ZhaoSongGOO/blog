# HAL - HardWare Abstract Layer

Android系统分两层来支持硬件设备，其中一层实现在用户空间中，另一层实现在内核空间中，Linux 内核自身的驱动模块就是在内核空间中，而HAL 就是另一个运行在用户空间的硬件驱动服务。

为什么要搞两层的硬件相关服务呢？

1. 兼容性，不同的移动厂商可以通过修改和扩展 HAL 来接入自己的硬件设备，而无需更改上游 Linux Kernel 内容。
2. 商业性，Linux Kernel 是 GPL 协议的，要求就是你如果修改了其代码，就需要把你的的代码公开，因此移动厂商为了保密自己的核心代码避免直接在 LK 中进行修改。

### 内核驱动开发

内核驱动是在内核加载的时候就会 load 到内核空间的一段代码，那驱动的作用是什么呢？

驱动往往用来驱动设备的运行，他是内核的扩展，可以将内核的命令转发给硬件，也可以将硬件的驱动上报给内核。另一方面，驱动提供了一个设备文件，一般放置在 /dev 目录下，这个文件是用户暴露到用户空间的接口，通过对文件的读写操作来操作驱动，进而控制硬件。


驱动分为硬件驱动和虚拟硬件驱动，顾名思义，硬件驱动往往和一个具体的硬件设备关联，虚拟硬件驱动则没有对应的硬件设备，只是一个运行在内核的代码逻辑。

在本小节，我们先学习一下内核驱动开发的方法，为了简化起见，我们只开发一个虚拟硬件驱动。

1. 仓库准备 

Android 提供了一个模拟器内核版本，叫 [goldfish](http://android.googlesource.com/kernel/goldfish)，我们就以这个内核进行开发。

```bash
git clone http://android.googlesource.com/kernel/goldfish
```

2. 编写驱动

目标：我们将为一个虚拟的字符硬件设备开发驱动程序。这个虚拟的字符硬件设备只有一个寄存器，它的大小为4字节，可读可写。由于这个字符设备是虚拟的，且只有一个寄存器，因此，我们将它称为“fake register”​，并且将对应的驱动程序命名为freg。

goldfish 有一个目录叫 drivers，这个目录下放置着所有的驱动，我们在其中新建一个目录 freg 用来放置我们这个驱动的代码。

- freg.h

没有什么固定的格式，只是定义一个我们需要的数据类型，其中 val 是虚拟寄存器存储，sem 是一个信号量，用以同步访问控制，dev 是一个字符设备描述结构。

```c
#ifndef _FAKE_REG_H_
#define _FAKE_REG_H_

#include <linux/cdev.h>
#include <linux/semaphore.h>

#define FREG_DEVICE_NODE_NAME  "freg"
#define FREG_DEVICE_FILE_NAME  "freg"
#define FREG_DEVICE_PROC_NAME  "freg"
#define FREG_DEVICE_CLASS_NAME "freg"

struct fake_reg_dev {
	int val;
	struct semaphore sem;
	struct cdev dev;
};

#endif
```

- freg.c

在 c 文件中我们就要遵循一定的规范来进行编码了，

首先 `module_init(freg_init);module_exit(freg_exit);` 用来注册模块加载以及卸载时执行的逻辑，例如，当我们内核加载 freg 的时候，就会执行 freg_init 函数。

刚才说了驱动都会在 /dev 下给用户生成一个设备文件，用以用户进行硬件访问，所以在 freg.c 中会声明这些文件设备访问回调。

```c
#include "freg.h"

static int freg_major = 0;
static int freg_minor = 0;

static struct class* freg_class = NULL;
static struct fake_reg_dev* freg_dev = NULL;


static int freg_open(struct inode* inode, struct file* filp);
static int freg_release(struct inode* inode, struct file* filp);
static ssize_t freg_read(struct file* filp, char __user *buf, size_t count, loff_t* f_pos);
static ssize_t freg_write(struct file* filp, const char __user *buf, size_t count, loff_t* f_pos);

// 定义文件操作回调函数，例如用户使用 open 打开 /dev/freg 的时候，会回调 freg_open 函数。
static struct file_operations freg_fops = {
    .owner = THIS_MODULE,
    .open = freg_open,
    .release = freg_release,
    .read = freg_read,
    .write = freg_write,
};

static int freg_open(struct inode* inode, struct file* filp) {
    struct fake_reg_dev* dev;
    // 用户使用 open 打开 /dev/freg 的时候，返回的是 inode 节点，我们需要推导出 fake_reg_dev 结构体指针，就是用这个 container_of 的宏。
    // inode->i_cdev 就是 struct cdev dev; 类型。
    dev = container_of(inode->i_cdev, struct fake_reg_dev, dev);
    filp->private_data = dev;
    return 0;
}

static int freg_release(struct inode* inode, struct file* filp) {
    return 0;
}

static ssize_t freg_read(struct file* filp, char __user *buf, size_t count, loff_t* f_pos) {
    ssize_t err = 0;
    struct fake_reg_dev* dev = filp->private_data;

    // 信号量-1，避免并发访问数据竞争
    if(down_interruptible(&(dev->sem))) {
        return -ERESTARTSYS;
    }
    // 如果用户提供的 buff 尺寸过小，就直接返回。
    if(count < sizeof(dev->val)) {
        goto out;
    }
    // 否则，将 val 的值拷贝到用户缓冲区
    if(copy_to_user(buf, &(dev->val), sizeof(dev->val))) {
        err = -EFAULT;
        goto out;
    }
    // 读取的数据尺寸
    err = sizeof(dev->val);
out:
    up(&(dev->sem));
    return err;
}

static ssize_t freg_write(struct file* filp, const char __user *buf, size_t count, loff_t* f_pos) {
    struct fake_reg_dev* dev = filp->private_data;
    ssize_t err = 0;

    if(down_interruptible(&(dev->sem))) {
        return -ERESTARTSYS;
    }

    if(count != sizeof(dev->val)) {
        goto out;
    }

    if(copy_from_user(&(dev->val), buf, count)) {
        err = -EFAULT;
        goto out;
    }

    err = sizeof(dev->val);

out:
    up(&(dev->sem));
    return err;
}

static int  __freg_setup_dev(struct fake_reg_dev* dev) {
    int err;
    dev_t devno = MKDEV(freg_major, freg_minor);

    memset(dev, 0, sizeof(struct fake_reg_dev));

    // 设置设备文件操作回调
    cdev_init(&(dev->dev), &freg_fops);
    dev->dev.owner = THIS_MODULE;
    dev->dev.ops = &freg_fops;

    err = cdev_add(&(dev->dev),devno, 1);
    if(err) {
        return err;
    }
    // 初始化信号量
    sema_init(&(dev->sem), 1);
    dev->val = 0;

    return 0;
}

static int __init freg_init(void) {
    int err = -1;
    dev_t dev = 0;
    struct device* temp = NULL;

    printk(KERN_ALERT"Initializing freg device.\n");

    // 获取设备号
    err = alloc_chrdev_region(&dev, 0, 1, FREG_DEVICE_NODE_NAME);
    if(err < 0) {
        printk(KERN_ALERT"Failed to alloc char dev region.\n");
        goto fail;
    }

    freg_major = MAJOR(dev);
    freg_minor = MINOR(dev);

    freg_dev = kmalloc(sizeof(struct fake_reg_dev), GFP_KERNEL);
    if(!freg_dev) {
        err = -ENOMEM;
        printk(KERN_ALERT"Failed to alloc freg device.\n");
        goto unregister;
    }
    // 初始化结构体
    err = __freg_setup_dev(freg_dev);
    if(err) {
        printk(KERN_ALERT"Failed to setup freg device: %d.\n", err);
        goto cleanup;
    }

    freg_class = class_create(THIS_MODULE, FREG_DEVICE_CLASS_NAME);
    if(IS_ERR(freg_class)) {
        err = PTR_ERR(freg_class);
        printk(KERN_ALERT"Failed to create freg device class.\n");
        goto destroy_cdev;
    }
    // 创建设备节点 ， 叫 /dev/freg
    temp = device_create(freg_class, NULL, dev, "%s", FREG_DEVICE_FILE_NAME);
    if(IS_ERR(temp)) {
        err = PTR_ERR(temp);
        printk(KERN_ALERT"Failed to create freg device.\n");
        goto destroy_class;
    }

    printk(KERN_ALERT"Succedded to initialize freg device.\n");

    return 0;

destroy_class:
    class_destroy(freg_class);
destroy_cdev:
    cdev_del(&(freg_dev->dev));
cleanup:
    kfree(freg_dev);
unregister:
    unregister_chrdev_region(MKDEV(freg_major, freg_minor), 1);
fail:
    return err;
}

static void __exit freg_exit(void) {
    dev_t devno = MKDEV(freg_major, freg_minor);

    printk(KERN_ALERT"Destroy freg device.\n");

    if(freg_class) {
        device_destroy(freg_class, MKDEV(freg_major, freg_minor));
        class_destroy(freg_class);
    }

    if(freg_dev) {
        cdev_del(&(freg_dev->dev));
        kfree(freg_dev);
    }

    unregister_chrdev_region(devno, 1);
}

MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Fake Register Driver");

module_init(freg_init);
module_exit(freg_exit);

```

- Kconfig

构建编译配置，这里主要关注  `default n` 代表默认不编译到内核中，而是在 make 的时候进行指定。

```txt
config FREG
	tristate "Fake Register Driver"
	default n
	help
	This is the freg driver for android system.
```

- Makefile

这是驱动程序freg的编译脚本文件，其中，$(CONFIG_FREG)是一个变量，它的值与驱动程序freg的编译选项有关。如果选择将驱动程序freg内建到内核中，那么变量$(CONFIG_FREG)的值为y；如果选择以模块的方式来编译驱动程序freg，那么变量$(CONFIG_FREG)的值为m；如果变量$(CONFIG_FREG)的值既不为y，也不为m，那么驱动程序freg就不会被编译。

```makefile
obj-$(CONFIG_FREG) += freg.o
```

- 系统构建配置

上面是驱动模块的源码以及编译配置，要想在内核编译的时候可以感知到我们自己编译的驱动，我们还需在系统的 Kconfig 和 Makefile 中进行处理。

首先在 drivers/Kconfig 文件中增加 "source drivers/freg/Kconfig" 以引入 freg 的编译 config。

其次在 drivers/Makefile 中增加 "obj-$(CONFIG_FREG) += freg/" 来将 freg 假如到编译依赖中。


### TODO: 内核内置 C 程序开发

### 开发 HAL 层模块

首先明确下，HAL 不属于 Kernel 了，而是在 AOSP 中维护，你在 golafish 中找不到了。

#### 规范

Android系统为硬件抽象层中的模块接口定义了编写规范，我们必须按照这个规范来编写自己的硬件模块接口，否则就会导致无法正常访问硬件。下面我们首先介绍硬件抽象层模块接口的编写规范，然后再按照这个规范为虚拟硬件设备freg开发硬件抽象层模块接口。

1. 硬件抽象层模块文件命名规范

我们的每一个硬件抽象层模块在系统中都是以动态链接库的形式存在，名称必须按照 `<MODULE_ID>.<Variant>.so` 的形式命名。

variant 的取值，来自于系统属性，有优先级顺序 `ro.hardware` > `ro.product.board` > `ro.board.platform` > `ro.arch`,系统会依次读取这四个属性的值，作为 variant。

假设你要加载 camera 模块（MODULE_ID 为 camera），系统会这样查找：

- 读取 `ro.hardware` 属性，比如值为 `msm8998`，查找 `camera.msm8998.so` 是否存在。
- 如果上一步没找到，读取 `ro.product.board`，比如值为 `dragon`，查找 `camera.dragon.so`。
- 依次尝试 `ro.board.platform` 和 `ro.arch`。
- 如果都找不到，最后查找 `camera.default.so`。

2. HAL 模块结构体定义规范

- 每一个 HAL 模块必须提供一个 HAL_MODULE_INFO_SYM 的结构体符号，并且这个结构体第一个成员必须是 hw_module_t 类型。
- 每个 hw_module_t 第一个字段 tag 内容是固定的 HARDWARE_MODULE_TAG，以标明其实一个 HAL 模块。
- 持有一个 dso，用来存储模块动态库 dlopen 打开后的句柄。
- 持有一个 hw_module_methods_t 类型的成员，用来获取一个 HAL 设备。
- hw_module_methods_t 提供了一个 open 方法来打开 HAL 设备 hw_device_t。
- hw_device_t 提供了 close 方法来关闭设备。



```c
/**
 * Every hardware module must have a data structure named HAL_MODULE_INFO_SYM
 * and the fields of this data structure must begin with hw_module_t
 * followed by module specific information.
 */
typedef struct hw_module_t {
    /** tag must be initialized to HARDWARE_MODULE_TAG */
    uint32_t tag;

    //...
    struct hw_module_methods_t* methods;

    /** module's dso */
    void* dso;
    //...
} hw_module_t;

typedef struct hw_module_methods_t {
    /** Open a specific device */
    int (*open)(const struct hw_module_t* module, const char* id,
            struct hw_device_t** device);

} hw_module_methods_t;

/**
 * Every device data structure must begin with hw_device_t
 * followed by module specific public methods and attributes.
 */
typedef struct hw_device_t {
    /** tag must be initialized to HARDWARE_DEVICE_TAG */
    uint32_t tag;
    //...

    /** reference to the module this device belongs to */
    struct hw_module_t* module;

    //...

    /** Close this device */
    int (*close)(struct hw_device_t* device);

} hw_device_t;

```

#### 编写 freg 的 HAL 模块

每一个硬件抽象层模块在内核中都对应有一个驱动程序，硬件抽象层模块就是通过这些驱动程序来访问硬件设备的，它们是通过读写设备文件来进行通信的。在本节我们就基于之前开发的 freg 内核驱动来编写对应的 HAL 模块。

在 Android 中，所有的 HAL 模块位于 `hardware/libhardware/modules` 下面。

1. 在 `hardware/libhardware/include` 下增加 freg.h

```c++
#ifndef ANDROID_FREG_INTERFACE_H
#define ANDROID_FREG_INTERFACE_H

#include <hardware/hardware.h>

__BEGIN_DECLS

/**
 * The id of this module
 */
#define FREG_HARDWARE_MODULE_ID "freg"

/**
 * The id of this device
 */
#define FREG_HARDWARE_DEVICE_ID "freg"

struct freg_module_t {
	struct hw_module_t common;
};

struct freg_device_t {
	struct hw_device_t common;
	int fd;
	int (*set_val)(struct freg_device_t* dev, int val);
	int (*get_val)(struct freg_device_t* dev, int* val);
};

__END_DECLS

#endif
```

2. 在 `hardware/libhardware/modules/` 增加 freg.cc

```cpp
#define DEVICE_NAME "/dev/freg"
#define MODULE_NAME "Freg"
#define MODULE_AUTHOR "shyluo@gmail.com"

static int freg_device_open(const struct hw_module_t* module, const char* id, struct hw_device_t** device);
static int freg_device_close(struct hw_device_t* device);
static int freg_set_val(struct freg_device_t* dev, int val);
static int freg_get_val(struct freg_device_t* dev, int* val);

static struct hw_module_methods_t freg_module_methods = {
	open: freg_device_open
};

struct freg_module_t HAL_MODULE_INFO_SYM = {
	common: {
		tag: HARDWARE_MODULE_TAG,	
		version_major: 1,
		version_minor: 0,
		id: FREG_HARDWARE_MODULE_ID,
		name: MODULE_NAME,
		author: MODULE_AUTHOR,
		methods: &freg_module_methods,
	}
};

static int freg_device_open(const struct hw_module_t* module, const char* id, struct hw_device_t** device) {
	if(!strcmp(id, FREG_HARDWARE_DEVICE_ID)) {
		struct freg_device_t* dev;

		dev = (struct freg_device_t*)malloc(sizeof(struct freg_device_t));
		if(!dev) {
			LOGE("Failed to alloc space for freg_device_t.");
			return -EFAULT;	
		}

		memset(dev, 0, sizeof(struct freg_device_t));

		dev->common.tag = HARDWARE_DEVICE_TAG;
		dev->common.version = 0;
		dev->common.module = (hw_module_t*)module;
		dev->common.close = freg_device_close;
		dev->set_val = freg_set_val;
		dev->get_val = freg_get_val;
	
		if((dev->fd = open(DEVICE_NAME, O_RDWR)) == -1) {
			LOGE("Failed to open device file /dev/freg -- %s.", strerror(errno));
			free(dev);
			return -EFAULT;
		}

		*device = &(dev->common);

		LOGI("Open device file /dev/freg successfully.");	

		return 0;
	}

	return -EFAULT;
}

static int freg_device_close(struct hw_device_t* device) {
	struct freg_device_t* freg_device = (struct freg_device_t*)device;
	if(freg_device) {
		close(freg_device->fd);
		free(freg_device);
	}

	return 0;
}

static int freg_set_val(struct freg_device_t* dev, int val) {
	if(!dev) {
		LOGE("Null dev pointer.");
		return -EFAULT;
	}

	LOGI("Set value %d to device file /dev/freg.", val);
	write(dev->fd, &val, sizeof(val));

	return 0;
}

static int freg_get_val(struct freg_device_t* dev, int* val) {
	if(!dev) {
		LOGE("Null dev pointer.");
		return -EFAULT;
	}
	
	if(!val) {
		LOGE("Null val pointer.");
		return -EFAULT;
	}

	read(dev->fd, val, sizeof(*val));

	LOGI("Get value %d from device file /dev/freg.", *val);

	return 0;
}
```

3. 增加编译配置 Android.mk

参数为$(BUILD_SHARED_LIBRARY)，表示要将该硬件抽象层模块编译成一个动态链接库文件，名称为freg.default，并且保存在$(TARGET_OUT_SHARED_LIBRARIES)/hw目录下，即out/target/product/generic/system/lib/hw目录下。

```txt
LOCAL_PATH := $(call my-dir)
include $(CLEAR_VARS)
LOCAL_MODULE_TAGS := optional
LOCAL_PRELINK_MODULE := false
LOCAL_MODULE_PATH := $(TARGET_OUT_SHARED_LIBRARIES)/hw
LOCAL_SHARED_LIBRARIES := liblog
LOCAL_SRC_FILES := freg.cpp
LOCAL_MODULE := freg.default
include $(BUILD_SHARED_LIBRARY)
```

### HAL 模块加载过程分析

对于我们定义好的 HAL module，我们可以直接使用系统提供的接口 `hw_get_module` 来进行加载。

```c
static const char *variant_keys[] = {
    "ro.hardware",  /* This goes first so that it can pick up a different
                       file on the emulator. */
    "ro.product.board",
    "ro.board.platform",
    "ro.arch"
};

static const int HAL_VARIANT_KEYS_COUNT =
    (sizeof(variant_keys)/sizeof(variant_keys[0]));

int hw_get_module_by_class(const char *class_id, const char *inst,
                           const struct hw_module_t **module)
{
    int i = 0;
    char prop[PATH_MAX] = {0};
    char path[PATH_MAX] = {0};
    char name[PATH_MAX] = {0};
    char prop_name[PATH_MAX] = {0};

    /* First try a property specific to the class and possibly instance */
    snprintf(prop_name, sizeof(prop_name), "ro.hardware.%s", name);
    if (property_get(prop_name, prop, NULL) > 0) {
        if (hw_module_exists(path, sizeof(path), name, prop) == 0) {
            goto found;
        }
    }

    /* Loop through the configuration variants looking for a module */
    for (i=0 ; i<HAL_VARIANT_KEYS_COUNT; i++) {
        if (property_get(variant_keys[i], prop, NULL) == 0) {
            continue;
        }
        if (hw_module_exists(path, sizeof(path), name, prop) == 0) {
            goto found;
        }
    }

    /* Nothing found, try the default */
    if (hw_module_exists(path, sizeof(path), name, "default") == 0) {
        goto found;
    }

    return -ENOENT;

found:
    /* load the module, if this fails, we're doomed, and we should not try
     * to load a different variant. */
    return load(class_id, path, module); // dlopen
}

int hw_get_module(const char *id, const struct hw_module_t **module)
{
    return hw_get_module_by_class(id, NULL, module);
}
```

### HAL 加载权限问题

我们在之前生成的 `/dev/freg` 文件用户程序没有权限打开，所以我们开发的 HAL 模块会报权限问题，Android 提供了 uevent 机制来对 `/dev/freg` 文件增加权限。可以在系统启动时修改设备文件的访问权限。

1. 在 AOSP 仓库的 `system/core/rootdir/ueventd.rc` 文件中增加权限并重新编译

```txt
/dev/freg 0666 root root
```

2. 不重编译，解包修改镜像文件

我们编译生成的 ramdisk.img 文件本身是一个 gzip 文件，可以先用 gzip 解压缩，得到 ramdisk.img cpio 文件。

```bash
mv ramdisk.img ramdisk.img.gz

gunzip ramdisk.img.gz
```

解压后的结果是一个 cpio 格式的文件，我们进一步使用 cpio 进行解压缩

```bash
cpio -i -F ramdisk.img
```

修改 ueventfd.rc 文件，重打包

### 开发系统硬件访问服务

到这里，我们已经在 HAL 中提供了对应的 freg 模块操作能力，有时，我们希望给应用层 APP 开发者提供能力访问 freg，因为权限以及兼容性原因，我们不能直接让 APP 通过 jni 来访问对应的 HAL 接口。

Android 的标准化做法是：

- HAL 以系统服务的方式注册在 SystemServer 进程。
- APP 使用 Binder RPC 来访问对应的系统服务。 

#### 定义 AIDL 接口

Android 提供了接口定义语言 AIDL，使用 AIDL 描述一个接口，Android 在编译时会扩展生成对应的服务端对象 Stub 和客户端代理 Proxy。

我们在 frameworks/base/core/java/android/os 目录下定义对应的 aidl 文件 IFregService.aidl。

最终在编译的时候，这个文件会生成对应的 IFregService.java 文件，并至于 framework.jar 中。

```java
package android.os;

interface IFregService {
	void setVal(int val);
	int getVal();
}
```

#### 实现 FregService 服务端

1. 在目录 frameworks/base/services/java/com/android/server/ 下实现 FregService.java 文件.

```java
package com.android.server;

import android.content.Context;
import android.os.IFregService;
import android.util.Slog;

public class FregService extends IFregService.Stub {
	private static final String TAG = "FregService";
	
	private int mPtr = 0;

	FregService() {
		mPtr = init_native();
		
		if(mPtr == 0) {
			Slog.e(TAG, "Failed to initialize freg service.");
		}
	}

	public void setVal(int val) {
		if(mPtr == 0) {
			Slog.e(TAG, "Freg service is not initialized.");
			return;
		}

		setVal_native(mPtr, val);
	}	

	public int getVal() {
		if(mPtr == 0) {
			Slog.e(TAG, "Freg service is not initialized.");
			return 0;
		}

		return getVal_native(mPtr);
	}
	
	private static native int init_native();
    private static native void setVal_native(int ptr, int val);
	private static native int getVal_native(int ptr);
}
```

2. 在 frameworks/base/services/jni 下实现对应的 jni native 代码

```cpp
#define LOG_TAG "FregServiceJNI"

#include "jni.h"
#include "JNIHelp.h"
#include "android_runtime/AndroidRuntime.h"

#include <utils/misc.h>
#include <utils/Log.h>
#include <hardware/hardware.h>
#include <hardware/freg.h>

#include <stdio.h>

namespace android
{
	static void freg_setVal(JNIEnv* env, jobject clazz, jint ptr, jint value) {
		freg_device_t* device = (freg_device_t*)ptr;
		if(!device) {
			LOGE("Device freg is not open.");
			return;
		}	
	
		int val = value;

		LOGI("Set value %d to device freg.", val);
		
		device->set_val(device, val);
	}

	static jint freg_getVal(JNIEnv* env, jobject clazz, jint ptr) {
		freg_device_t* device = (freg_device_t*)ptr;
		if(!device) {
			LOGE("Device freg is not open.");
			return 0;
		}

		int val = 0;

		device->get_val(device, &val);
		
		LOGI("Get value %d from device freg.", val);
	
		return val;
	}

	static inline int freg_device_open(const hw_module_t* module, struct freg_device_t** device) {
		return module->methods->open(module, FREG_HARDWARE_DEVICE_ID, (struct hw_device_t**)device);
	}
	
	static jint freg_init(JNIEnv* env, jclass clazz) {
		freg_module_t* module;
		freg_device_t* device;
		
		LOGI("Initializing HAL stub freg......");

		if(hw_get_module(FREG_HARDWARE_MODULE_ID, (const struct hw_module_t**)&module) == 0) {
			LOGI("Device freg found.");
			if(freg_device_open(&(module->common), &device) == 0) {
				LOGI("Device freg is open.");
				return (jint)device;
			}

			LOGE("Failed to open device freg.");
			return 0;
		}

		LOGE("Failed to get HAL stub freg.");

		return 0;		
	}

	static const JNINativeMethod method_table[] = {
		{"init_native", "()I", (void*)freg_init},
		{"setVal_native", "(II)V", (void*)freg_setVal},
		{"getVal_native", "(I)I", (void*)freg_getVal},
	};

	int register_android_server_FregService(JNIEnv *env) {
    		return jniRegisterNativeMethods(env, "com/android/server/FregService", method_table, NELEM(method_table));
	}
};
```

#### 服务端注册

1. 加载 jni 库，SystemService 进程在初始化的时候，会加载 libandroid_servers 动态库，并调用其中的 JNI_OnLoad 方法，这个方法会注册 JNI 方法，因此我们需要在 frameworks/base/services/jni/onload.cpp 中调用 register_android_server_FregService 方法注册对应的服务 jni。

```cpp
extern "C" jint JNI_OnLoad(JavaVM* vm, void* reserved)
{
    JNIEnv* env = NULL;
    jint result = -1;

    if (vm->GetEnv((void**) &env, JNI_VERSION_1_4) != JNI_OK) {
        LOGE("GetEnv failed!");
        return result;
    }
    LOG_ASSERT(env, "Could not retrieve the env!");
    //...
    register_android_server_FregService(env);

    return JNI_VERSION_1_4;
}
```

2. 我们开发的 FregService 是一个 Java 服务，还需要在 SystemService java 层进行注册才行。

在 frameworks/base/services/java/com/android/server/SystemServer.java 文件中进行 addService。

```java
try {
    Slog.i(TAG, "Freg Service");
    ServiceManager.addService("freg", new FregService());
} catch (Throwable e) {
    Slog.e(TAG, "Failure starting Freg Service", e);
}
```

#### 客户端实现

这里的客户端实现就是APP开发者如何在 APP 中使用刚才的 FregService。

```java
package shy.luo.freg;

import android.os.IFregService;

public class Freg extends Activity  {
	private IFregService fregService = null;
	
    /** Called when the activity is first created. */
    @Override
    public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.main);

	    fregService = IFregService.Stub.asInterface(ServiceManager.getService("freg"));
        
        valueText = (EditText)findViewById(R.id.edit_value);
        readButton = (Button)findViewById(R.id.button_read);
        writeButton = (Button)findViewById(R.id.button_write);
        clearButton = (Button)findViewById(R.id.button_clear);

        //  int val = fregService.getVal();

        // fregService.setVal(val);
    }
}
```

