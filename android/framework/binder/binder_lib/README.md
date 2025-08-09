# Binder 进程间通信库

> 对应的进程间通信库版本是 android-2.3.2_r1

## BnInterface & BpInterface

`BnInterface` 对应的是 binder 实体对象，即 binder_node，`BpInterface` 对应的是 binder 引用对象。

`INTERFACE` 是一个模版参数，由用户自己注入，代表 Service 组件接口，用户数组的这个接口需要实现 IInterface。

```cpp
template<typename INTERFACE>
class BnInterface : public INTERFACE, public BBinder
{
public:
    virtual sp<IInterface>      queryLocalInterface(const String16& _descriptor);
    virtual const String16&     getInterfaceDescriptor() const;

protected:
    virtual IBinder*            onAsBinder();
};

// ----------------------------------------------------------------------

template<typename INTERFACE>
class BpInterface : public INTERFACE, public BpRefBase
{
public:
                                BpInterface(const sp<IBinder>& remote);

protected:
    virtual IBinder*            onAsBinder();
};
```

## BBinder

BBinder 类有两个重要的成员函数 transact 和 onTransact。当一个 Binder 代理对象通过 Binder 驱动程序向一个 Binder 本地对象发出一个进程间通信请求时，Binder 驱动程序就会调用该 Binder 本地对象的成员函数 transact 来处理该请求。成员函数 onTransact 是由 BBinder 的子类，即 Binder 本地对象类来实现的，它负责分发与业务相关的进程间通信请求。

```cpp
class BBinder : public IBinder
{
public:
    //...

    virtual status_t    transact(   uint32_t code,
                                    const Parcel& data,
                                    Parcel* reply,
                                    uint32_t flags = 0);

    //...

protected:
    //...

    virtual status_t    onTransact( uint32_t code,
                                    const Parcel& data,
                                    Parcel* reply,
                                    uint32_t flags = 0);

    //...
};
```

## BpRefBase

模板类BpInterface继承了BpRefBase类，后者为Binder代理对象提供了抽象的进程间通信接口。

BpRefBase 类有一个重要的成员变量 mRemote，它指向一个 BpBinder 对象，可以通过成员函数remote来获取。

```cpp
class BpRefBase : public virtual RefBase
{
protected:
                            BpRefBase(const sp<IBinder>& o);
    virtual                 ~BpRefBase();
    virtual void            onFirstRef();
    virtual void            onLastStrongRef(const void* id);
    virtual bool            onIncStrongAttempted(uint32_t flags, const void* id);

    inline  IBinder*        remote()                { return mRemote; }
    inline  IBinder*        remote() const          { return mRemote; }

private:
                            BpRefBase(const BpRefBase& o);
    BpRefBase&              operator=(const BpRefBase& o);

    IBinder* const          mRemote;
    RefBase::weakref_type*  mRefs;
    volatile int32_t        mState;
};
```

## BpBinder

BpBinder 类的成员变量 mHandle 是一个整数，它表示一个 Client 组件的句柄值，可以通过成员函数 handle 来获取。

binder_ref 里面有一个成员叫 desc，就是这个 mHandle。

```cpp
class BpBinder : public IBinder
{
public:
                        BpBinder(int32_t handle);

    inline  int32_t     handle() const { return mHandle; }

    // ...

    virtual status_t    transact(   uint32_t code,
                                    const Parcel& data,
                                    Parcel* reply,
                                    uint32_t flags = 0);

    //...

private:
    const   int32_t             mHandle;

    //...
};
```

BpBinder 类的成员函数 transact 用来向运行在 Server 进程中的 Service 组件发送进程间通信请求，这是通过 Binder 驱动程序间接实现的。BpBinder 类的成员函数transact 会把 BpBinder 类的成员变量 mHandle，以及进程间通信数据发送给 Binder 驱动程序，这样 Binder 驱动程序就能够根据这个句柄值来找到对应的 Binder 引用对象，继而找到对应的 Binder 实体对象，最后就可以将进程间通信数据发送给对应的 Service 组件了。


## IPCThreadState(线程级)

代表了单个线程与 Binder 驱动的交互状态。每个与 Binder 通信的线程都有 自己独立的一个 `IPCThreadState` 实例（通过线程局部存储 Thread Local Storage 实现）。

IPCThreadState 屏蔽了 binder 驱动的细节，用于其余对象与 binder 驱动进行通信。它一方面负责向 Binder 驱动程序发送进程间通信请求，另一方面又负责接收来自 Binder 驱动程序的进程间通信请求。

```cpp
class IPCThreadState
{
public:
    static  IPCThreadState*     self();
    
            sp<ProcessState>    process();
            //...
            
            status_t            transact(int32_t handle,
                                         uint32_t code, const Parcel& data,
                                         Parcel* reply, uint32_t flags);
            //...
private: 
    //...
    const   sp<ProcessState>    mProcess;
    //...
};
```

## ProcessState(进程级)

代表了你的服务进程与整个 Android Binder 系统的连接。

对于每一个使用了 Binder 进程间通信机制的进程来说，它的内部都有一个 ProcessState 对象，它负责初始化 Binder 设备，即打开设备文件 /dev/binder，以及将设备文件 /dev/binder 映射到进程的地址空间。由于这个 ProcessState 对象在进程范围内是唯一的，因此，Binder 线程池中的每一个线程都可以通过它来和 Binder 驱动程序建立连接。

第一次调用 ProcessState 类的静态成员函数 self 时，Binder 库就会为进程创建一个 ProcessState 对象，并且调用函数 open 来打开设备文件 /dev/binder，接着又调用函数 mmap 将它映射到进程的地址空间，即请求 Binder 驱动程序为进程分配内核缓冲区。设备文件 /dev/binder 映射到进程的地址空间后，得到的内核缓冲区的用户地址就保存在其成员变量 mVMStart 中。

```cpp
class ProcessState : public virtual RefBase
{
public:
    static  sp<ProcessState>    self();

    //...
            
private:
    //...

            int                 mDriverFD;
            void*               mVMStart;
            
    //...
};
```

## 类图

1. Service 组件实现原理

<img src="android/framework/binder/binder_lib/resources/1.png" style="width:80%">

2. Client 组件实现原理

<img src="android/framework/binder/binder_lib/resources/2.png" style="width:80%">