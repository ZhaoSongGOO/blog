# Binder C++ 实现

## C++ 实现方案

1. 定义通信协议。
2. 服务端协议和主流程实现。
3. 客户端协议和主流程实现。


### 定义通信协议

```cpp
// 通信协议需要继承自 IInterface 接口
class ICustomService: public IInterface {
public:
    //DECLARE_META_INTERFACE 是一个宏，声明了一些变量和函数
    DECLARE_META_INTERFACE(CustomService);
    virtual void action1() = 0;
    virtual int action2(const char *name) = 0;
};
```

### 服务端协议和主流程实现

```cpp
//声明
//ICustomService.h
class BnCustomService: public BnInterface<ICustomService> {

public:
    //服务端收到数据后的回调
    status_t onTransact(uint32_t code, const Parcefl& data, Parcel* reply, uint32_t lags = 0);
    void action1();
    int action2(const char *name);
};


//实现
//BnCustomService.cpp
#define LOG_TAG "BnCustomService"
#include <log/log.h>
#include "ICustomService.h"


//服务端收到数据的回调
status_t BnCustomService::onTransact(uint32_t code, const Parcel& data, Parcel* reply, uint32_t flags) {
    //code 表示客户端需要调用哪个函数
    switch(code) {
        //调用 sayhello
        case HELLO_SVR_CMD_ACTION1:  {
            //调用 action1 函数
            action1();
            //写入回复给客户端的数据
            reply->writeInt32(0);
            return NO_ERROR;
        } break;
        //调用 sayhelloto
        case HELLO_SVR_CMD_ACTION@: {
            //取出客户端发送的参数
            int32_t policy =  data.readInt32();
			String16 name16_tmp = data.readString16(); 

			String16 name16 = data.readString16();
			String8 name8(name16);
            //调用 action2 函数
			int cnt = action2(name8.string());
            //写入回复给客户端的数据
			reply->writeInt32(0); 
			reply->writeInt32(cnt);

            return NO_ERROR;
        } break;
  
        default:
            return BBinder::onTransact(code, data, reply, flags);
  
    }
}

//服务端函数的具体实现
void BnCustomService::action1() {
    static int count = 0;
    ALOGI("say hello :%d\n ", ++count);
}

int BnCustomService::action2(const char *name) {
    static int cnt = 0;
	ALOGI("say hello to %s : %d\n", name, ++cnt);
	return cnt;
}


int main(int argc, char const *argv[])
{
    //使用 ProcessState 类完成 binder 驱动的初始化
    sp<ProcessState> proc(ProcessState::self());
    //注册服务
    sp<IServiceManager> sm = defaultServiceManager();
    sm->addService(String16("custom"), new BnCustomService());
    //开启 binder 线程池
	ProcessState::self()->startThreadPool();
    //加入线程池
	IPCThreadState::self()->joinThreadPool();
    return 0;
}
```

### 客户端协议和主流程实现

```cpp
//客户端
//ICustomService.h
class BpCustomClient: public BpInterface<ICustomService> {
public:
    BpCustomClient(const sp<IBinder>& impl);
    void sayHello();
    int sayHelloTo(const char *name);
};


//BpCustomClient.cpp
#include "ICustomService.h"

//调用父类构造函数
BpCustomClient::BpCustomClient(const sp<IBinder>& impl):BpInterface<ICustomService>(impl) {

}

void BpCustomClient::action1() {
    Parcel data, reply;
    data.writeInt32(0);
    data.writeString16(String16("ICustomService"));
    //发起远程调用
    remote()->transact(HELLO_SVR_CMD_ACTION1, data, &reply);
}

int BpCustomClient::action2(const char *name) {
    Parcel data, reply;
    int exception;

    data.writeInt32(0);
    data.writeString16(String16("ICustomService"));
    data.writeString16(String16(name));
    //发起远程调用
    remote()->transact(HELLO_SVR_CMD_ACTION2, data, &reply);
    exception = reply.readInt32();
	if (exception)
		return -1;
	else
		return reply.readInt32();
    IMPLEMENT_META_INTERFACE(HelloService, "ICustomService");
}

int main(int argc, char const *argv[])
{
    //使用 ProcessState 类完成 binder 驱动的初始化
    sp<ProcessState> proc(ProcessState::self());
    //获取 hello 服务
    sp<IServiceManager> sm = defaultServiceManager();
    //返回的是 BpBinder 指针
    sp<IBinder> binder = sm->getService(String16("custom"));
    sp<CustomService> service = interface_cast<CustomService>(binder);

    if (binder == 0)
	{
		ALOGI("can't get custom service\n");
		return -1;
	}

    //发起远程调用
    service->action1();
    int cnt = service->action2("nihao");
	ALOGI("client call action2, cnt = %d", cnt);

    return 0;
}
```

## C++ 代码解析

在 binder 中一般服务端对象以 `Bn` 开头，意思是 binder native。客户端对象以 `Bp` 开头，意思是 binder proxy。

<img src="aosp/binder/resources/binder_8.png"/>


## 增加 Native 系统服务回调

## Java 系统服务实现

## Java 调用 Native 服务

## Native 调用 Java 服务

## Binder 多线程情景分析

## Binder 对象泄露

## Binder 死亡通知

## Binder 异常处理机制

