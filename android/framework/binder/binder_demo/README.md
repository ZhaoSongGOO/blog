# Binder 通信举例

本小节基于之前 hal 接收中实现的 freg 虚拟设备驱动开发一个系统服务。

在开发一个 native 层的系统服务的时候，我们有这几个模块需要去实现：
1. 基于 `IInterface` 完成服务接口定义，例如 `ServiceInterface。`
2. 基于 `BnInterface<ServiceInterface>` 实现服务端处理逻辑。
3. 基于 `BpInterface<ServiceInterface>` 实现客户端处理逻辑。

## 服务接口定义

```cpp
#define FREG_SERVICE "test.FregService"

class IFregService: public IInterface {
public:
    DECLARE_META_INTERFACE(FregService);
    virtual int32_t getVal() = 0;
    virtual void setVal(int32_t val) = 0;
};

IMPLEMENT_META_INTERFACE(FregService, "test.FregService.descriptor")
```

其中 `DECLARE_META_INTERFACE` 和 `IMPLEMENT_META_INTERFACE` 的内容如下：

```cpp
#define DECLARE_META_INTERFACE(INTERFACE)                               \
    static const android::String16 descriptor;                          \
    static android::sp<I##INTERFACE> asInterface(                       \
            const android::sp<android::IBinder>& obj);                  \
    virtual const android::String16& getInterfaceDescriptor() const;    \
    I##INTERFACE();                                                     \
    virtual ~I##INTERFACE();                                            \

#define IMPLEMENT_META_INTERFACE(INTERFACE, NAME)                       \
    const android::String16 I##INTERFACE::descriptor(NAME);             \
    const android::String16&                                            \
            I##INTERFACE::getInterfaceDescriptor() const {              \
        return I##INTERFACE::descriptor;                                \
    }                                                                   \
    android::sp<I##INTERFACE> I##INTERFACE::asInterface(                \
            const android::sp<android::IBinder>& obj)                   \
    {                                                                   \
        android::sp<I##INTERFACE> intr;                                 \
        if (obj != NULL) {                                              \
            intr = static_cast<I##INTERFACE*>(                          \
                obj->queryLocalInterface(                               \
                        I##INTERFACE::descriptor).get());               \
            if (intr == NULL) {                                         \
                intr = new Bp##INTERFACE(obj);                          \
            }                                                           \
        }                                                               \
        return intr;                                                    \
    }                                                                   \
    I##INTERFACE::I##INTERFACE() { }                                    \
    I##INTERFACE::~I##INTERFACE() { }                                   \
```

成员函数 asInterface 的参数 obj 应该指向一个类型为 BnFregService 的 Binder 本地对象，或者一个类型为 BpBinder 的 Binder 代理对象；否则，它的返回值就会等于 NULL。如果参数指向的是一个 BnFregService 对象，那么调用它的成员函数 queryLocalInterface 就可以直接返回一个 IFregService 接口；如果参数 obj 指向的是一个 BpBinder 代理对象，那么它的成员函数 queryLocalInterface 的返回值就为 NULL，因此，接着就会将该 BpBinder 代理对象封装成一个BpFregService 对象，并且将它的 IFregService 接口返回给调用者。


## BnInterface\<ServiceInterface\> 定义

```cpp
class BnFregService: public BnInterface<IFregService> {
public:
    virtual status_t onTransact(uint32_t code, const Parcel &data, Parcel *replay, uint32_t flags = 0);
};

status_t BnFregService::onTransact(uint32_t code, const Parcel &data, Parcel *replay, uint32_t flags){
    switch(code){
        case GTE_VAL:{
            CHECK_INTERFACE(IFregService, data, replay);
            int32_t val = getVal();
            replay->writeInt32(val);
            return NO_ERROR;
        }
        case SET_VAL:{
            CHECK_INTERFACE(IFregService, data, replay);
            int32_t val = data.readInt32();
            setVal(val);
            return NO_ERROR;
        }
        default:{
            return BBinder::onTransact(code, data, replay, flags);
        }
    }
}
```

BnFregService 类的成员函数 onTransact 在将 GET_VAL 和 SET_VAL 进程间通信请求分发给其子类处理之前，会首先调用宏 CHECK_INTERFACE 来检查该进程间通信请求的合法性，即检查该请求是否是由 FregService 组件的代理对象发送过来的。如果是，那么传递过来的 Parcel 对象 data 中的第一个数据应该是一个 IFregService 接口描述符，即 "test.FregService.descriptor"​；如果不是，那么 BnFregService 类的成员函数 onTransact 就会认为这是一个非法的进程间通信请求，因此，就不会继续向下执行了。

## BpInterface\<ServiceInterface\> 定义

```cpp
enum {
    GET_VAL = IBinder::FIRST_CALL_TRANSACTION,
    SET_VAL
};

class BpFregService: public BpInterface<IFregService> {
public:
    BpFregService(const sp<IBinder> & impl)
        :BpInterface<IFregService>(impl){

    }

    int32_t getVal() {
        Parcel data;
        data.writeInterfaceToken(IFregService.getInterfaceDescriptor());
        Parcel replay;
        remote()->transact(GET_VAL, data, &replay);
        int32_t val = replay.readInt32();
        return val;
    }
    
    void setVal(int32_t val){
        Parcel data;
        data.writeInterfaceToken(IFregService.getInterfaceDescriptor());
        data.writeInt32(val);
        Parcel replay;
        remote()->transact(SET_VAL, data, &replay);
    }

};
```

## 服务端进程实现

```cpp
class FregService: public BnFregService {
public:
    FregService() {
        // open fd
    }

    ~FregService() {
        // close fd 
    }

    int32_t getVal() {
        // get value from driver
        return value;
    }

    void setVal(int32_t val) {
        // set value to driver
    }
};

int main() {
    defaultServiceManager() -> addService(String16(FREG_SERVICE), new FregService());
    // 启动一个Binder线程池，最后第65行调用主线程的IPCThreadState对象的成员函数
    ProcessState::self()->startThreadPool();
    // 将主线程添加到进程的Binder线程池中，用来处理来自Client进程的通信请求。
    IPCThreadState::self()->joinThreadPool();
    return 0;
}

```

## 客户端进程实现

```cpp

int main() {
    sp<IBinder> binder = defaultServiceManager()->getService(String16(FREG_SERVICE));
    if(binder == NULL){
        return -1;
    }

    sp<IFregService> service = IFregService::asInterface(binder);

    if(service == NULL){
        return -1;
    }

    int32_t val = service->getVal();

    val += 1;

    service->setVal(val);

    return 0;
}
```








