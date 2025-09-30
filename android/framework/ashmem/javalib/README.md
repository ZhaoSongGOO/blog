# AshMem Javalib 库

Android Java 库 提供了 MemoryFile 类来使用 ashmem 共享内存服务。

## 创建

这个类包含两个构造方法，两个构造方法大部分的逻辑都是通过 jni 触发 c++ 执行。

```java
public MemoryFile(String name, int length) throws IOException {
    mLength = length;
    mFD = native_open(name, length);
    mAddress = native_mmap(mFD, length, PROT_READ | PROT_WRITE);
    mOwnsRegion = true;
}
public MemoryFile(FileDescriptor fd, int length, String mode) throws IOException {
    if (fd == null) {
        throw new NullPointerException("File descriptor is null.");
    }
    if (!isMemoryFile(fd)) {
        throw new IllegalArgumentException("Not a memory file.");
    }
    mLength = length;
    mFD = fd;
    mAddress = native_mmap(mFD, length, modeToProt(mode));
    mOwnsRegion = false;
}
public static boolean isMemoryFile(FileDescriptor fd) throws IOException {
    return (native_get_size(fd) >= 0);
}
```

### native_get_size

首先讲一个 jobject 类型的文件描述符解析出来 c++ 的文件描述符，随后调用 cutils 的方法 ashmem_get_size_region。

```cpp
static jint android_os_MemoryFile_get_size(JNIEnv* env, jobject clazz,
        jobject fileDescriptor) {
    int fd = jniGetFDFromFileDescriptor(env, fileDescriptor);
    // Use ASHMEM_GET_SIZE to find out if the fd refers to an ashmem region.
    // ASHMEM_GET_SIZE should succeed for all ashmem regions, and the kernel
    // should return ENOTTY for all other valid file descriptors
    int result = ashmem_get_size_region(fd);
    if (result < 0) {
        if (errno == ENOTTY) {
            // ENOTTY means that the ioctl does not apply to this object,
            // i.e., it is not an ashmem region.        }
        // Some other error, throw exception
        jniThrowIOException(env, errno);
        return (jint) -1;
    }
    return (jint) result;
    }
}
```

### native_open

很简单，调用 cutils 方法 ashmem_create_region 获取文件描述符，返回 jobject 类型的文件描述符。

```cpp
static jobject android_os_MemoryFile_open(JNIEnv* env, jobject clazz, jstring name, jint length)
{
    const char* namestr = (name ? env->GetStringUTFChars(name, NULL) : NULL);

    int result = ashmem_create_region(namestr, length);

    if (name)
        env->ReleaseStringUTFChars(name, namestr);

    if (result < 0) {
        jniThrowException(env, "java/io/IOException", "ashmem_create_region failed");
        return NULL;
    }

    return jniCreateFileDescriptor(env, result);
}
```

### native_mmap

使用 mmap 完成地址空间的映射。

```cpp
static jint android_os_MemoryFile_mmap(JNIEnv* env, jobject clazz, jobject fileDescriptor,
        jint length, jint prot)
{
    int fd = jniGetFDFromFileDescriptor(env, fileDescriptor);
    jint result = (jint)mmap(NULL, length, prot, MAP_SHARED, fd, 0);
    if (!result)
        jniThrowException(env, "java/io/IOException", "mmap failed");
    return result;
}
```

## 读写

MemeoryFile 的方法 readBytes 和 writeBytes 方法用来读写共享内存的内容。在读取或者写入一块匿名共享内存时，首先要保证这块匿名共享内存已经映射到进程的地址空间中，这是通过调用成员函数 isDeactivated 来判断的。

MemoryFile 类有一个成员变量 mAllowPurging，它是一个布尔变量。如果它的值等于 true，那么就表示每次访问 MemoryFile 类内部的匿名共享内存之后，都要将它解锁，以便它可以被内存管理系统回收。在函数 android_os_MemoryFile_read 和 android_os_MemoryFile_write 中，参数 unpinned 的值就对应于 MemoryFile 类的成员变量 mAllowPurging 的值；因此，当它等于 true 时，这两个 JNI 方法就需要调用运行时库 cutils 提供的函数 ashmem_pin_region 来判断 MemoryFile 类内部的匿名共享内存是否已经被内存管理系统回收。

如果函数 ashmem_pin_region 的返回值等于 ASHMEM_WAS_PURGED，就说明这块匿名共享内存已经被内存管理系统回收了，这时候这两个 JNI 方法就会返回一个错误代码-1 给调用者，表示它们不能够再访问 MemoryFile 类内部的匿名共享内存了。如果 MemoryFile 类内部的匿名共享内存还没有被内存管理系统回收，那么就可以正常访问它的内容了。访问结束之后，如果发现参数 unpinned 的值等于 true，那么第 15 行和第 34 行还需要将这块匿名共享内存解锁，以便在系统内存不足时，内存管理系统可以将它回收。

```java
public int readBytes(byte[] buffer, int srcOffset, int destOffset, int count) 
        throws IOException {
    if (isDeactivated()) {
        throw new IOException("Can't read from deactivated memory file.");
    }
    if (destOffset < 0 || destOffset > buffer.length || count < 0
            || count > buffer.length - destOffset
            || srcOffset < 0 || srcOffset > mLength
            || count > mLength - srcOffset) {
        throw new IndexOutOfBoundsException();
    }
    return native_read(mFD, mAddress, buffer, srcOffset, destOffset, count, mAllowPurging);
}

public void writeBytes(byte[] buffer, int srcOffset, int destOffset, int count)
        throws IOException {
    if (isDeactivated()) {
        throw new IOException("Can't write to deactivated memory file.");
    }
    if (srcOffset < 0 || srcOffset > buffer.length || count < 0
            || count > buffer.length - srcOffset
            || destOffset < 0 || destOffset > mLength
            || count > mLength - destOffset) {
        throw new IndexOutOfBoundsException();
    }
    native_write(mFD, mAddress, buffer, srcOffset, destOffset, count, mAllowPurging);
}

// 判断是不是已经 mmap 过共享内存
private boolean isDeactivated() {
    return mAddress == 0;
}
```

对应的 cpp 方法。

```cpp
static jint android_os_MemoryFile_read(JNIEnv* env, jobject clazz,
        jobject fileDescriptor, jint address, jbyteArray buffer, jint srcOffset, jint destOffset,
        jint count, jboolean unpinned)
{
    int fd = jniGetFDFromFileDescriptor(env, fileDescriptor);
    if (unpinned && ashmem_pin_region(fd, 0, 0) == ASHMEM_WAS_PURGED) {
        ashmem_unpin_region(fd, 0, 0);
        jniThrowException(env, "java/io/IOException", "ashmem region was purged");
        return -1;
    }

    env->SetByteArrayRegion(buffer, destOffset, count, (const jbyte *)address + srcOffset);

    if (unpinned) {
        ashmem_unpin_region(fd, 0, 0);
    }
    return count;
}

static jint android_os_MemoryFile_write(JNIEnv* env, jobject clazz,
        jobject fileDescriptor, jint address, jbyteArray buffer, jint srcOffset, jint destOffset,
        jint count, jboolean unpinned)
{
    int fd = jniGetFDFromFileDescriptor(env, fileDescriptor);
    if (unpinned && ashmem_pin_region(fd, 0, 0) == ASHMEM_WAS_PURGED) {
        ashmem_unpin_region(fd, 0, 0);
        jniThrowException(env, "java/io/IOException", "ashmem region was purged");
        return -1;
    }

    env->GetByteArrayRegion(buffer, srcOffset, count, (jbyte *)address + destOffset);

    if (unpinned) {
        ashmem_unpin_region(fd, 0, 0);
    }
    return count;
}
```

