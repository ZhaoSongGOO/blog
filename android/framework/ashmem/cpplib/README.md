# 匿名内存的 C++ 接口

Android 系统在应用程序框架层中提供了两个 C++类 MemoryHeapBase 和 MemoryBase 来创建和管理匿名共享内存。如果一个进程需要与其他进程共享一块完整的匿名共享内存，那么它就可以使用 MemoryHeapBase 类创建这块匿名共享内存。如果一个进程创建了一块匿名共享内存之后，只希望与其他进程共享其中的一部分，那么它就可以使用 MemoryBase 类来创建这块匿名共享内存。

MemoryHeapBase 本质是一个 binder service 组件的实现，将它们实例化之后就得到一个 Service 组件，从而可以用来执行进程间通信，即将一块匿名共享内存从一个进程传输到另一个进程。


## MemoryHeapBase

### server 实现

> <img src="android/framework/ashmem/resources/3.png" style="width:70%">

#### IMemoryHeap

```cpp
class IMemoryHeap : public IInterface
{
public:
    DECLARE_META_INTERFACE(MemoryHeap);

    // flags returned by getFlags()
    enum {
        READ_ONLY   = 0x00000001
    };
    // 获取匿名共享内存块的文件描述符
    virtual int         getHeapID() const = 0;
    // 获取映射地址
    virtual void*       getBase() const = 0;
    // 获取大小
    virtual size_t      getSize() const = 0;
    // 获取访问保护位
    virtual uint32_t    getFlags() const = 0;

    // these are there just for backward source compatibility
    int32_t heapID() const { return getHeapID(); }
    void*   base() const  { return getBase(); }
    size_t  virtualSize() const { return getSize(); }
};
```

#### BnMemoryHeap

```cpp
class BnMemoryHeap : public BnInterface<IMemoryHeap>
{
public:
    virtual status_t onTransact( 
            uint32_t code,
            const Parcel& data,
            Parcel* reply,
            uint32_t flags = 0);
    
    BnMemoryHeap();
protected:
    virtual ~BnMemoryHeap();
};

/*
分别调用由其子类重写的成员函数 getHeapID、getSize 和 getFlags 来获取一个匿名共享内存块的文件描述符、大小和访问保护位，
并且将它们写入到 Parcel 对象 reply 中，以便可以将它们返回给 Client 进程。
*/

status_t BnMemoryHeap::onTransact(
        uint32_t code, const Parcel& data, Parcel* reply, uint32_t flags)
{
    switch(code) {
       case HEAP_ID: {
            CHECK_INTERFACE(IMemoryHeap, data, reply);
            reply->writeFileDescriptor(getHeapID());
            reply->writeInt32(getSize());
            reply->writeInt32(getFlags());
            return NO_ERROR;
        } break;
        default:
            return BBinder::onTransact(code, data, reply, flags);
    }
}
```

#### MemoryHeapBase

```cpp
class MemoryHeapBase : public virtual BnMemoryHeap 
{
public:
    //...
    MemoryHeapBase(size_t size, uint32_t flags = 0, char const* name = NULL);

    virtual ~MemoryHeapBase();

    /* implement IMemoryHeap interface */
    virtual int         getHeapID() const;
    virtual void*       getBase() const;
    virtual size_t      getSize() const;
    virtual uint32_t    getFlags() const;

    //...   

private:
    //...
    /*
    mFD 是一个文件描述符，它是打开设备文件/dev/ashmem 后得到的，用来描述一个匿名共享内存块；
    成员变量 mSize、mBase 和 mFlags 分别用来描述这块匿名共享内存块的大小、映射地址和访问保护位。  
    */
    int         mFD;
    size_t      mSize;
    void*       mBase;
    uint32_t    mFlags;
    //...
};
```

实例化的时候建立与 ashmem 驱动的关系。

```cpp
MemoryHeapBase::MemoryHeapBase(size_t size, uint32_t flags, char const * name)
    : mFD(-1), mSize(0), mBase(MAP_FAILED), mFlags(flags),
      mDevice(0), mNeedUnmap(false)
{
    const size_t pagesize = getpagesize();
    size = ((size + pagesize-1) & ~(pagesize-1));
    int fd = ashmem_create_region(name == NULL ? "MemoryHeapBase" : name, size);
    LOGE_IF(fd<0, "error creating ashmem region: %s", strerror(errno));
    if (fd >= 0) {
        if (mapfd(fd, size) == NO_ERROR) {
            if (flags & READ_ONLY) {
                ashmem_set_prot_region(fd, PROT_READ);
            }
        }
    }
}

status_t MemoryHeapBase::mapfd(int fd, size_t size, uint32_t offset)
{
    //...

    if ((mFlags & DONT_MAP_LOCALLY) == 0) {
        void* base = (uint8_t*)mmap(0, size,
                PROT_READ|PROT_WRITE, MAP_SHARED, fd, offset);
        if (base == MAP_FAILED) {
            //...
            close(fd);
            return -errno;
        }
        mBase = base;
        mNeedUnmap = true;
    } else  {
        mBase = 0; // not MAP_FAILED
        mNeedUnmap = false;
    }
    mFD = fd;
    mSize = size;
    return NO_ERROR;
}

// 对应服务函数的实现
int MemoryHeapBase::getHeapID() const {
    return mFD;
}

void* MemoryHeapBase::getBase() const {
    return mBase;
}

size_t MemoryHeapBase::getSize() const {
    return mSize;
}

uint32_t MemoryHeapBase::getFlags() const {
    return mFlags;
}
```

### client 实现

> <img src="android/framework/ashmem/resources/4.png" style="width:70%">


#### BpMemoryHeap

```cpp
class BpMemoryHeap : public BpInterface<IMemoryHeap>
{
public:
    BpMemoryHeap(const sp<IBinder>& impl);
    //...

    virtual int getHeapID() const;
    virtual void* getBase() const;
    virtual size_t getSize() const;
    virtual uint32_t getFlags() const;

    //...

    mutable volatile int32_t mHeapId;
    mutable void*       mBase;
    mutable size_t      mSize;
    mutable uint32_t    mFlags;
    //...
};
```

这个 Bp 对象的几个虚方法实现如下。

```cpp
int BpMemoryHeap::getHeapID() const {
    assertMapped();
    return mHeapId;
}

void* BpMemoryHeap::getBase() const {
    assertMapped();
    return mBase;
}

size_t BpMemoryHeap::getSize() const {
    assertMapped();
    return mSize;
}

uint32_t BpMemoryHeap::getFlags() const {
    assertMapped();
    return mFlags;
}
```

其中 assertMap 的实现如下。当这四个成员函数的其中一个第一次被调用时，成员函数 assertMapped 就会被调用来请求运行在 Server 端的 MemoryHeapBase 服务，返回其内部的匿名共享内存块的文件描述符、大小和访问保护位，以便可以将这块匿名共享内存映射到 Client 进程的地址空间。

```cpp
void BpMemoryHeap::assertMapped() const
{   
    // 如果 mHeapId == -1 意味着服务端的匿名内存块还没映射到 client 进程的地址空间。
    if (mHeapId == -1) {
        // 尝试获取缓存的信息，缓存以 binder 代理对象为 key 存储。
        sp<IBinder> binder(const_cast<BpMemoryHeap*>(this)->asBinder());
        sp<BpMemoryHeap> heap(static_cast<BpMemoryHeap*>(find_heap(binder).get()));
        // 请求运行在 Server 端的 MemoryHeapBase 服务返回其内部的匿名共享内存块的信息，并且将该匿名共享内存块映射到 Client 进程的地址空间；
        // 最后就得到该匿名共享内存块在 Client 进程的映射地址、大小和文件描述符了，分别保存在 MemoryHeapBase 代理对象 heap 的成员变量 mBase、mSize 和 mHeapId 中。
        heap->assertReallyMapped();
        if (heap->mBase != MAP_FAILED) {
            Mutex::Autolock _l(mLock);
            if (mHeapId == -1) {
                mBase   = heap->mBase;
                mSize   = heap->mSize;
                android_atomic_write( dup( heap->mHeapId ), &mHeapId );
            }
        } else {
            // something went wrong
            free_heap(binder);
        }
    }
}
```

随后我们看 `assertReallyMapped` 的实现。通过成员函数 remote 来获得该 MemoryHeapBase 代理对象内部的 Binder 代理对象，接着再调用这个 Binder 代理对象的成员函数 transact 向运行在 Server 端的
MemoryHeapBase 服务发送一个类型为 HEAP_ID 的进程间通信请求，即请求该 MemoryHeapBase 服务返回其内部的匿名共享内存的文件描述符、大小和访问保护位。

MemoryHeapBase 服务将其内部的匿名共享内存的文件描述符经过 Binder 驱动程序返回给 Client 进程时，Binder 驱动程序会在 Client 进程中复制这个文件描述符，使得它指向 MemoryHeapBase 服务中的匿名共享内存。

获得了一个指向运行在 Server 端的 MemoryHeapBase 服务内部的匿名共享内存的文件描述符之后，接着就可以调用函数 mmap 将这块匿名共享内存映射到 Client 进程的地址空间，最后就可以获得它的地址，并且保存在成员变量 mBase 中。这样，Client 进程就可以通过这个地址来访问这块匿名共享内存了，即与 Server 端共享了同一块匿名共享内存。

```cpp
void BpMemoryHeap::assertReallyMapped() const
{
    if (mHeapId == -1) {
        //...
        Parcel data, reply;
        data.writeInterfaceToken(IMemoryHeap::getInterfaceDescriptor());
        status_t err = remote()->transact(HEAP_ID, data, &reply);
        int parcel_fd = reply.readFileDescriptor();
        ssize_t size = reply.readInt32();
        uint32_t flags = reply.readInt32();

        //...

        int fd = dup( parcel_fd );
        //...

        int access = PROT_READ;
        if (!(flags & READ_ONLY)) {
            access |= PROT_WRITE;
        }

        Mutex::Autolock _l(mLock);
        if (mHeapId == -1) {
            mRealHeap = true;
            // 把对应的 fd 再 mmap 到应用进程来。
            mBase = mmap(0, size, access, MAP_SHARED, fd, 0);
            if (mBase == MAP_FAILED) {
                //...
                close(fd);
            } else {
                mSize = size;
                mFlags = flags;
                android_atomic_write(fd, &mHeapId);
            }
        }
    }
}
```

## MemoryBase

> <img src="android/framework/ashmem/resources/5.png" style="width:70%">

MemoryBase 类内部有一个类型为 IMemoryHeap 的强指针 mHeap，它指向一个 MemoryHeapBase 服务，MemoryBase 类就是通过它来描述一个匿名共享内存服务的。MemoryBase 类所维护的匿名共享内存其实只是其内部的 MemoryHeapBase 服务所维护的匿名共享内存中的一小块。

这一小块匿名共享内存用另外两个成员变量 mOffset 和 mSize 来描述；其中，mOffset 表示这一小块匿名共享内存在一块完整的匿名共享内存中的偏移值，mSize 则表示这一小块匿名共享内存的大小。


### Server 实现

> <img src="android/framework/ashmem/resources/6.png" style="width:70%">

#### IMemory

```cpp
class IMemory : public IInterface
{
public:
    DECLARE_META_INTERFACE(Memory);

    virtual sp<IMemoryHeap> getMemory(ssize_t* offset=0, size_t* size=0) const = 0;

    //...
    void* pointer() const;
    size_t size() const;
    ssize_t offset() const;
};

// 获取虚拟内存空间地址
void* IMemory::pointer() const {
    ssize_t offset;
    sp<IMemoryHeap> heap = getMemory(&offset);
    void* const base = heap!=0 ? heap->base() : MAP_FAILED;
    if (base == MAP_FAILED)
        return 0;
    return static_cast<char*>(base) + offset;
}

size_t IMemory::size() const {
    size_t size;
    getMemory(NULL, &size);
    return size;
}

ssize_t IMemory::offset() const {
    ssize_t offset;
    getMemory(&offset);
    return offset;
}
```

#### BnMemory

BnMemory 继承了 IMemory 接口，用来处理远程请求。

```cpp
status_t BnMemory::onTransact(
    uint32_t code, const Parcel& data, Parcel* reply, uint32_t flags)
{
    switch(code) {
        case GET_MEMORY: {
            CHECK_INTERFACE(IMemory, data, reply);
            ssize_t offset;
            size_t size;
            reply->writeStrongBinder( getMemory(&offset, &size)->asBinder() );
            reply->writeInt32(offset);
            reply->writeInt32(size);
            return NO_ERROR;
        } break;
        default:
            return BBinder::onTransact(code, data, reply, flags);
    }
}
```

#### MemoryBase

MemoryBase 继承了 BnMemory, 并实现了 getMemory 方法。很简单，就是返回了自己内部的 MemoryHeapBase 对象指针。

```cpp
sp<IMemoryHeap> MemoryBase::getMemory(ssize_t* offset, size_t* size) const
{
    if (offset) *offset = mOffset;
    if (size)   *size = mSize;
    return mHeap;
}
```

### Client 实现

> <img src="android/framework/ashmem/resources/7.png" style="width:70%">

MemoryBase 类在 Client 端主要是实现一个类型为 BpMemory 的 Client 组件，即一个实现了 IMemory 接口的 Binder 代理对象，通过它可以获得运行在 Server 端的 MemoryBase 服务内部的一小块匿名共享内存的偏移值和大小，以及一个 MemoryHeapBase 代理对象。有了这个 MemoryHeapBase 代理对象之后，Client 端就可以将在 Server 端创建的一块匿名共享内存映射到自己的地址空间了。


#### BpMemory

成员变量 mHeap 指向一个 MemoryHeapBase 代理对象；成员变量 mOffset 和 mSize 分别用来描述一小块匿名共享内存的偏移值和大小。

```cpp
class BpMemory : public BpInterface<IMemory>
{
public:
    BpMemory(const sp<IBinder>& impl);
    virtual ~BpMemory();
    virtual sp<IMemoryHeap> getMemory(ssize_t* offset=0, size_t* size=0) const;
    
private:
    mutable sp<IMemoryHeap> mHeap;
    mutable ssize_t mOffset;
    mutable size_t mSize;
};
```

我们看其核心方法，getMemory 方法的实现。

```cpp
sp<IMemoryHeap> BpMemory::getMemory(ssize_t* offset, size_t* size) const
{
    if (mHeap == 0) {
        Parcel data, reply;
        data.writeInterfaceToken(IMemory::getInterfaceDescriptor());
        if (remote()->transact(GET_MEMORY, data, &reply) == NO_ERROR) {
            sp<IBinder> heap = reply.readStrongBinder();
            ssize_t o = reply.readInt32();
            size_t s = reply.readInt32();
            if (heap != 0) {
                mHeap = interface_cast<IMemoryHeap>(heap);
                if (mHeap != 0) {
                    mOffset = o;
                    mSize = s;
                }
            }
        }
    }
    if (offset) *offset = mOffset;
    if (size) *size = mSize;
    return mHeap;
}
```
