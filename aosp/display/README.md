# 显示系统

<img src="aosp/display/resources/d_1.png" style="width:100%"/>

1. App 中 Add 一个 `DecorView` 时（`DecorView` 是一棵 View 树，用于承载 Window 中显示的具体内容），WMS 中会创建一个 `WindowContainer`（或者 `WindowContainer` 的子类）对象，`WindowContainer` 们通过树结构组织在一起。在 WMS 的角度 `WindowContainer` 就是一个图层。

2. 在 WMS 中，每一个 `WindowContainer` 的构建过程中会创建一个与之对应的 `SurfaceControl` 对象，`SurfaceControl` 用于管理 `Surface`，我们可以认为一个 `SurfaceControl` 就代表一个 `Surface`。

3. 在 WMS 中，创建 `SurfaceControl` 的时候，会向 `SurfaceFlinger` 发起 Binder 远程调用，`SurfaceFlinger` 进程中会创建一个与 SurfaceControl/Surface 相对应的 Layer 对象。Layer 在 SurfaceFlinger 进程中，用于表示一个图层。`SurfaceControl` 中有一个 handle 成员（Binder Bp 对象），通过这个 handle 可以索引到对应的 Layer 对象。SurfaceControl/surface 的作用，主要是将 App 中的 `View`，WMS 中的 `WindowContainer`，还有 `SurfaceFlinger` 中的 `Layer` 几个对象关联起来。

4. 当 `WindowContainer` SurfaceControl Layer 对象构建完成后，就会将 `SurfaceControl` 通过 Binder 返回给 App。App 拿到 SurfaceControl 之后，可以通过 SurfaceControl 获取到 `Surface` 对象。Surface 是帧缓存的实际持有者，通过 `Canvas` 对象对外提供绘制帧缓存的接口。当 App 刚拿到 Surface 时，内部还没有对应的帧缓存，会去创建一个 `BLASTBufferQueue` 对象，用于申请和提交帧缓存。每次要使用 Surface 的 Canvas 进行绘制前，需要先调用 `dequeue` 函数向 BLASTBufferQueue 申请一块内存（buffer），接着将 Canvas 绘制指令转换为图像数据并写入刚申请的内存中。这个向 BLASTBufferQueue 申请 Buffer 并写入图像数据的过程，可以认为是生产阶段。随后，向 BLASTBufferQueue 提交（enqueue） 这个 buffer，BLASTBufferQueue 将 buffer 提交给 SurfaceFlinger 去合成显示。这个阶段，可以理解为 Buffer 的消费阶段。

## 直接访问 SurfaceFliger 绘制

### Native Demo

```cpp
#define LOG_TAG "DisplayDemo"
// ...

using namespace android;
bool mQuit = false;

/*
 Android 系统支持多种显示设备，比如说，输出到手机屏幕，或者通过WiFi 投射到电视屏幕。Android用 DisplayDevice 类来表示这样的设备。不是所有的 Layer 都会输出到所有的Display, 比如说，我们可以只将Video Layer投射到电视， 而非整个屏幕。LayerStack 就是为此设计，LayerStack 是一个Display 对象的一个数值， 而类Layer里成员State结构体也有成员变量mLayerStack， 只有两者的mLayerStack 值相同，Layer才会被输出到给该Display设备。所以LayerStack 决定了每个Display设备上可以显示的Layer数目。   
 */
int mLayerStack = 0;

void fillRGBA8Buffer(uint8_t* img, int width, int height, int stride, int r, int g, int b) {
    for (int y = 0; y < height; y++) {
        for (int x = 0; x < width; x++) {
            uint8_t* pixel = img + (4 * (y*stride + x));
            pixel[0] = r;
            pixel[1] = g;
            pixel[2] = b;
            pixel[3] = 0;
        }
    }
}


int main(int argc, char ** argv) {

    // 建立 App 到 SurfaceFlinger 的 Binder 通信通道
    sp<SurfaceComposerClient> surfaceComposerClient = new SurfaceComposerClient;
    
    status_t err = surfaceComposerClient->initCheck();
    if (err != OK) {
        ALOGD("SurfaceComposerClient::initCheck error: %#x\n", err);
        return -1;
    }


    // 获取到显示设备的 ID
    // 返回的是一个 vector，因为存在多屏或者投屏等情况
    const std::vector<PhysicalDisplayId> ids = SurfaceComposerClient::getPhysicalDisplayIds();
    if (ids.empty()) {
        ALOGE("Failed to get ID for any displays\n");
        return -1;
    }   

    //displayToken 是屏幕的索引
    sp<IBinder> displayToken = nullptr;
    
    // 示例仅考虑只有一个屏幕的情况
    displayToken = SurfaceComposerClient::getPhysicalDisplayToken(ids.front());
    
    // 获取屏幕相关参数
    ui::DisplayMode displayMode;
    err = SurfaceComposerClient::getActiveDisplayMode(displayToken, &displayMode);
    if (err != OK)
        return -1;    

    
    ui::Size resolution = displayMode.resolution; 
    //resolution = limitSurfaceSize(resolution.width, resolution.height);

    // 创建 SurfaceControl 对象
    // 会远程调用到 SurfaceFlinger 进程中，Surfaceflinger 中会创建一个 Layer 对象
    String8 name("displaydemo");
    sp<SurfaceControl> surfaceControl = 
            surfaceComposerClient->createSurface(name, resolution.getWidth(), 
                                                    resolution.getHeight(), PIXEL_FORMAT_RGBA_8888,
                                                    ISurfaceComposerClient::eFXSurfaceBufferState,/*parent*/ nullptr);

    
    // 构建事务对象并提交
    SurfaceComposerClient::Transaction{}
            .setLayer(surfaceControl, std::numeric_limits<int32_t>::max())
            .show(surfaceControl)
            .setBackgroundColor(surfaceControl, half3{0, 0, 0}, 1.0f, ui::Dataspace::UNKNOWN) // black background
            .setAlpha(surfaceControl, 1.0f)
            .setLayerStack(surfaceControl, ui::LayerStack::fromValue(mLayerStack))
            .apply();


    // 初始化一个 BLASTBufferQueue 对象，传入了前面获取到的 surfaceControl
    // BLASTBufferQueue 是帧缓存的大管家
    sp<BLASTBufferQueue> mBlastBufferQueue = new BLASTBufferQueue("DemoBLASTBufferQueue", surfaceControl , 
                                             resolution.getWidth(), resolution.getHeight(),
                                             PIXEL_FORMAT_RGBA_8888);
                                             
    // 获取到 GraphicBuffer 的生产者并完成初始化。
    sp<IGraphicBufferProducer> igbProducer;
    igbProducer = mBlastBufferQueue->getIGraphicBufferProducer();
    igbProducer->setMaxDequeuedBufferCount(2);
    IGraphicBufferProducer::QueueBufferOutput qbOutput;
    igbProducer->connect(new StubProducerListener, NATIVE_WINDOW_API_CPU, false, &qbOutput);

    while(!mQuit) {
        int slot;
        sp<Fence> fence;
        sp<GraphicBuffer> buf;
        
        // 向 gralloc HAL 发起 binder 远程调用，分配内存
        // 核心是 GraphicBuffer 的初始化，以及 GraphicBuffer 的跨进程传输
        // 1. dequeue buffer
        igbProducer->dequeueBuffer(&slot, &fence, resolution.getWidth(), resolution.getHeight(),
                                              PIXEL_FORMAT_RGBA_8888, GRALLOC_USAGE_SW_WRITE_OFTEN,
                                              nullptr, nullptr);
        igbProducer->requestBuffer(slot, &buf);

        int waitResult = fence->waitForever("dequeueBuffer_EmptyNative");
        if (waitResult != OK) {
            ALOGE("dequeueBuffer_EmptyNative: Fence::wait returned an error: %d", waitResult);
            break;
        }
        
        // 2. fill the buffer with color
        uint8_t* img = nullptr;
        err = buf->lock(GRALLOC_USAGE_SW_WRITE_OFTEN, (void**)(&img));
        if (err != NO_ERROR) {
            ALOGE("error: lock failed: %s (%d)", strerror(-err), -err);
            break;
        }
        int countFrame = 0;
        countFrame = (countFrame+1)%3;
        
        fillRGBA8Buffer(img, resolution.getWidth(), resolution.getHeight(), buf->getStride(),
                        countFrame == 0 ? 255 : 0,
                        countFrame == 1 ? 255 : 0,
                        countFrame == 2 ? 255 : 0);

        err = buf->unlock();
        if (err != NO_ERROR) {
            ALOGE("error: unlock failed: %s (%d)", strerror(-err), -err);
            break;
        }
        
        // 3. queue the buffer to display
        IGraphicBufferProducer::QueueBufferOutput qbOutput;
        IGraphicBufferProducer::QueueBufferInput input(systemTime(), true /* autotimestamp */,
                                                       HAL_DATASPACE_UNKNOWN, {},
                                                       NATIVE_WINDOW_SCALING_MODE_FREEZE, 0,
                                                       Fence::NO_FENCE);
        igbProducer->queueBuffer(slot, input, &qbOutput);

        sleep(1);
    }
    return 0;
}
```

### SurfaceFlinger 服务初始化

#### 基础信息

`SurfaceFlinger` 是一个由 init 进程初始化的原生服务。整个服务的主要逻辑位于 `frameworks/native/services/surfaceflinger/main_surfaceflinger.cpp`。


#### 初始化 binder 驱动

```cpp
sp<ProcessState> ps(ProcessState::self()); // 初始化 binder 驱动
ps->startThreadPool(); // 开启线程池
```

#### 初始化 SurfaceFlinger 对象

```cpp
sp<SurfaceFlinger> flinger = surfaceflinger::createSurfaceFlinger();


sp<SurfaceFlinger> createSurfaceFlinger() {
    static DefaultFactory factory;

    return sp<SurfaceFlinger>::make(factory);
}
```

<img src="aosp/display/resources/d_2.png" style="width:100%"/>

- ISurfaceComposer 是一个接口，定义了 SurfaceFlinger 作为一个 Binder 服务对外提供的服务
- ComposerCallback 是 HWC 模块的回调，这个包含了三个很关键的回调函数，
    - onComposerHotplug 函数表示显示屏热插拔事件
    - onComposerHalRefresh 函数表示 Refresh 事件
    - onComposerHalVsync 表示 Vsync 信号事件。
- 持有 CompositionEngine 主要充当了 SurfaceFlinger 与 RenderEngine & HWComposer 之间的桥梁。
    - HWComposer 一方面向 SurfaceFlinger 提供硬件 Vsync 信号，另一方面用于 Device 合成 Layer 图层，也就是硬件合成。
    - RenderEngine 主要用于 Client 合成 Layer 图层，也就是软件合成。


#### 注册 binder 服务

```cpp
// .....
sp<IServiceManager> sm(defaultServiceManager());
sm->addService(String16(SurfaceFlinger::getServiceName()), flinger, false,
                IServiceManager::DUMP_FLAG_PRIORITY_CRITICAL | IServiceManager::DUMP_FLAG_PROTO);

// ......
// publish gui::ISurfaceComposer, the new AIDL interface
sp<SurfaceComposerAIDL> composerAIDL = sp<SurfaceComposerAIDL>::make(flinger);
// 注册了一个叫 SurfaceFlingerAIDL 的 binder 服务
sm->addService(String16("SurfaceFlingerAIDL"), composerAIDL, false,
                IServiceManager::DUMP_FLAG_PRIORITY_CRITICAL | IServiceManager::DUMP_FLAG_PROTO); 

// ......
```
#### 启动显示服务

```cpp
/*
这里会注册一个显示服务，Framework 层很少会接触到 DisplayService，DisplayService 实际是一个 hidl hal，
定义在 frameworks/native/services/displayservice 目录下，其主要作用是向其他 Vendor 模块提供显示器的 
hotplug 事件 和 Vsync 信号。
*/
static void startDisplayService() {
    using android::frameworks::displayservice::V1_0::implementation::DisplayService;
    using android::frameworks::displayservice::V1_0::IDisplayService;

    sp<IDisplayService> displayservice = sp<DisplayService>::make();
    status_t err = displayservice->registerAsService();

    // b/141930622
    if (err != OK) {
        ALOGE("Did not register (deprecated) IDisplayService service.");
    }
}
```

Display 接口定义，

```java
package android.frameworks.displayservice@1.0;

interface IEventCallback {
    /**
     * Vsync事件
     */
    oneway onVsync(uint64_t timestamp, uint32_t count);

    /**
     * hotplug事件
     */
    oneway onHotplug(uint64_t timestamp, bool connected);
};


package android.frameworks.displayservice@1.0;

import IEventCallback;

interface IDisplayEventReceiver {
    /**
     * 添加callback，开始接收Events事件，热插拔是默认打开的，Vysnc需要通过setVsyncRate打开
     */
    init(IEventCallback callback) generates (Status status);

    /**
     * 开始或停止发送callback
     */
    setVsyncRate(int32_t count) generates (Status status);

    /**
     * 请求一个Vsync，如果setVsyncRate是0，这不起作用
     */
    requestNextVsync() generates (Status status);

    /**
     * Server端丢弃所以的callback，停止发送
     */
    close() generates (Status status);
};
```

#### 进入循环等待

```cpp
// /frameworks/native/services/surfaceflinger/Scheduler/Scheduler.h
class Scheduler : android::impl::MessageQueue {
    //.......
}

// /frameworks/native/services/surfaceflinger/Scheduler/Scheduler.cpp
void Scheduler::run() {
    while (true) {
        waitMessage();
    }
}

// /frameworks/native/services/surfaceflinger/Scheduler/MessageQueue.cpp
void MessageQueue::waitMessage() {
    do {
        IPCThreadState::self()->flushCommands();
        int32_t ret = mLooper->pollOnce(-1);
        switch (ret) {
            case Looper::POLL_WAKE:
            case Looper::POLL_CALLBACK:
                continue;
            case Looper::POLL_ERROR:
                ALOGE("Looper::POLL_ERROR");
                continue;
            case Looper::POLL_TIMEOUT:
                // timeout (should not happen)
                continue;
            default:
                // should not happen
                ALOGE("Looper::pollOnce() returned unknown status %d", ret);
                continue;
        }
    } while (true);
}
```

### App 与 SurfaceFlinger 之间的 Binder 通信通道建立

SurfaceComposerClient 是一个 App 与 SurfaceFlinger 通信的辅助类，我们首先构造了这样一个辅助类，创建这个类的时候，会创建连接。

```cpp
int main(int argc, char ** argv) {
    sp<SurfaceComposerClient> surfaceComposerClient = new SurfaceComposerClient;
    status_t err = surfaceComposerClient->initCheck();
    if (err != OK) {
        ALOGD("SurfaceComposerClient::initCheck error: %#x\n", err);
        return;
    }

    // ......
}
```

构造函数中没有过多的操作。

```cpp
SurfaceComposerClient::SurfaceComposerClient() : mStatus(NO_INIT) {}
```

SurfaceComposerClient 在被第一次引用的时候，会调用 `onFirstRef` 函数。在这个函数中调用 `getComposerService` 方法。

```cpp
void SurfaceComposerClient::onFirstRef() {
    sp<gui::ISurfaceComposer> sf(ComposerServiceAIDL::getComposerService());
    if (sf != nullptr && mStatus == NO_INIT) {
        sp<ISurfaceComposerClient> conn;
        binder::Status status = sf->createConnection(&conn);
        if (status.isOk() && conn != nullptr) {
            mClient = conn;
            mStatus = NO_ERROR;
        }
    }
}
```
`getComposerService` 会调用 `connectLocked` 方法来初始化内部的成员 `ISurfaceComposer` 并返回。 `ISurfaceComposer` 是一个 binder 服务的代理。

```cpp
class ComposerServiceAIDL : public Singleton<ComposerServiceAIDL> {

    sp<gui::ISurfaceComposer> mComposerService;
    sp<IBinder::DeathRecipient> mDeathObserver;
    mutable std::mutex mMutex;

    ComposerServiceAIDL();
    bool connectLocked();
    void composerServiceDied();
    friend class Singleton<ComposerServiceAIDL>;

public:
    // Get a connection to the Composer Service.  This will block until
    // a connection is established. Returns null if permission is denied.
    static sp<gui::ISurfaceComposer> getComposerService();
};

// /frameworks/native/libs/gui/SurfaceComposerClient.cpp

/*static*/ sp<gui::ISurfaceComposer> ComposerServiceAIDL::getComposerService() {
    // 获取单例对象
    ComposerServiceAIDL& instance = ComposerServiceAIDL::getInstance();
    std::scoped_lock lock(instance.mMutex);
    if (instance.mComposerService == nullptr) {
        // 调用 connectLocked 获取 binder 服务
        if (ComposerServiceAIDL::getInstance().connectLocked()) {
            ALOGD("ComposerServiceAIDL reconnected");
            WindowInfosListenerReporter::getInstance()->reconnect(instance.mComposerService);
        }
    }
    return instance.mComposerService;
}
```

```cpp
bool ComposerServiceAIDL::connectLocked() {
    const String16 name("SurfaceFlingerAIDL");
    // 向 sm 获取到 SurfaceFlingerAIDL binder 服务代理端
    mComposerService = waitForService<gui::ISurfaceComposer>(name);
    if (mComposerService == nullptr) {
        return false; // fatal error or permission problem
    }

    // Create the death listener.
    class DeathObserver : public IBinder::DeathRecipient {
        ComposerServiceAIDL& mComposerService;
        virtual void binderDied(const wp<IBinder>& who) {
            ALOGW("ComposerService aidl remote (surfaceflinger) died [%p]", who.unsafe_get());
            mComposerService.composerServiceDied();
        }

    public:
        explicit DeathObserver(ComposerServiceAIDL& mgr) : mComposerService(mgr) {}
    };
    
    // 注册死亡通知
    mDeathObserver = new DeathObserver(*const_cast<ComposerServiceAIDL*>(this));
    IInterface::asBinder(mComposerService)->linkToDeath(mDeathObserver);
    return true;
}
```

随后调用 ComposerServiceAIDL 的 createConnection 方法，来获取匿名 Binder 服务。整体过程如下：

1. App 向 ServiceManager 查询 SurfaceFlingerAIDL 服务，获取到服务的代理端对象
2. 接着远程调用 SurfaceFlingerAIDL 服务的 createConnection 函数，获取到 Client 匿名服务的代理端对象
3. App 想要调用 SurfaceFlinger 相关的功能，可以远程调用 Client 服务，Client 服务中具体的功能再委托给 SurfaceFlinger 来实现。

### 显示信息配置获取与 SurfaceControl 初始化


分析代码之前，我们先了解 SurfaceControl 创建过程中涉及到的类：

- Surface 对象用于在 Native App 中描述一个图层，每一个 Surface 对象与 SurfaceControl 相关联，可以认为 Surface 和 SurfaceControl 是等价的
- Layer 对象用于在 SurfaceFlinger 中描述一个图层。
- 一个 Surface 对应一个 Layer
- SurfaceFlinger 是一个独立的 Service， 它接收 Surface 作为输入，根据 Z-Order， 透明度，大小，位置等参数，构建一个对应的 Layer 对象，计算出每个 Layer 在最终合成图像中的位置，然后在 sf-Vysnc 信号到来时，sf 将 Layer 交给 HWComposer 生成最终的显示 Buffer, 然后显示到特定的显示设备上。


#### surfaceComposerClient->createSurface

首先我们在 native app 中发起这个远端调用，这个远端调用会返回一个 `SurfaceControl` 对象。

```cpp
sp<SurfaceControl> surfaceControl = surfaceComposerClient->createSurface(mName, resolution.getWidth(), 
                                                                            resolution.getHeight(), PIXEL_FORMAT_RGBA_8888,
                                                                            ISurfaceComposerClient::eFXSurfaceBufferState,
                                                                            /*parent*/ nullptr);


// SurfaceControl 结构体内容

class SurfaceControl : public RefBase
{

// ......

private:
    // can't be copied
    SurfaceControl& operator = (SurfaceControl& rhs);
    SurfaceControl(const SurfaceControl& rhs);

    friend class SurfaceComposerClient;
    friend class Surface;

    ~SurfaceControl();

    sp<Surface> generateSurfaceLocked();
    status_t validate() const;

    // 应用创建的SurfaceComposerClient对象指针，里面封装了和SurfaceFlinger通信的Binder客户端对象
    sp<SurfaceComposerClient>   mClient;  
    // layer handle
    // 对应的 SF 进程中的 Layer 的索引
    sp<IBinder> mHandle;
    mutable Mutex               mLock;
    // SurfaceControl 对应的 Surface
    mutable sp<Surface>         mSurfaceData;  
    // BLASTBufferQueue 实例
    mutable sp<BLASTBufferQueue> mBbq; 
    // SurfaceControl 的子节点 ？
    mutable sp<SurfaceControl> mBbqChild;
    int32_t mLayerId = 0;
    std::string mName;
    uint32_t mTransformHint = 0;
    uint32_t mWidth = 0;
    uint32_t mHeight = 0;
    PixelFormat mFormat = PIXEL_FORMAT_NONE;
    uint32_t mCreateFlags = 0;
    uint64_t mFallbackFrameNumber = 100;
    std::shared_ptr<Choreographer> mChoreographer;
};
```

接下来调用服务端的 `createSurface` 函数。这个函数会返回一个 `CreateSurfaceResult`, 随后调用方(应用侧)根据这个 result 来构建 `SurfaceControl`.
在这个函数中，会使用 SurfaceFlinger  createLayer 创建对应的图层对象。

```cpp
// /frameworks/native/services/surfaceflinger/Client.h
sp<SurfaceFlinger> mFlinger;

// /frameworks/native/services/surfaceflinger/Client.cpp
binder::Status Client::createSurface(const std::string& name, int32_t flags,
                                     const sp<IBinder>& parent, const gui::LayerMetadata& metadata,
                                     gui::CreateSurfaceResult* outResult) {

    // We rely on createLayer to check permissions.
    sp<IBinder> handle;
    LayerCreationArgs args(mFlinger.get(), sp<Client>::fromExisting(this), name.c_str(),
                           static_cast<uint32_t>(flags), std::move(metadata));
    // handle 放到了 LayerCreationArgs 中，这个 handle 是我们即将要创建的 Layer 的父 Layer 的索引
    // 需要注意的是 CreateSurfaceResult 中也有一个 handle，这个是我们要创建的 Layer 的索引
    args.parentHandle = parent;
    // 接着调用 SurfaceFlinger 的 createLayer 函数
    const status_t status = mFlinger->createLayer(args, *outResult);
    return binderStatusFromStatusT(status);
}
```

#### createLayer

```cpp
status_t SurfaceFlinger::createBufferStateLayer(LayerCreationArgs& args, sp<IBinder>* handle,
                                                sp<Layer>* outLayer) {
    args.textureName = getNewTexture();
    *outLayer = getFactory().createBufferStateLayer(args);
    *handle = (*outLayer)->getHandle();
    return NO_ERROR;
}
```

1. 调用工厂函数构造 layer. 
3. 将创建好的 layer 及相关信息保存到 SurfaceFlinger 的成员变量中。其中最重要的成员是 mCreatedLayers，当下次 VSync 信号到来，读取这些数据配置新的 Layer 对象并合成显示。
2. 返回一个 handler 对象，handle 的类型是 LayerHandle，是一个 Binder 服务端对象。这个 handle 最终会返回给 App 端，是一个索引，app 可以将其传递给 sf 找到对应的 Layer。

#### 图层属性设置

app 向 surfaceflinger 提交事务之后，surfaceflinger 会缓存事务；当 vsync 到来之后，会取出事务并处理。

```cpp
SurfaceComposerClient::Transaction{}
        .setLayer(surfaceControl, std::numeric_limits<int32_t>::max())
        .show(surfaceControl)
        .setBackgroundColor(surfaceControl, half3{0, 0, 0}, 1.0f, ui::Dataspace::UNKNOWN) // black background
        .setAlpha(surfaceControl, 1.0f)
        .setLayerStack(surfaceControl, ui::LayerStack::fromValue(mLayerStack)) // mLayerStack 的值为 0
        .apply();
```

### BLASTBufferQueue 初始化

`BLASTBufferQueue` 的作用：

<img src="aosp/display/resources/d_3.png" style="width:50%"/>

1. App 调用 dequebuffer 向 BLASTBufferQueue 申请一个 buffer.
2. App 拿到 buffer 后开始渲染，所谓渲染就是把显示指令转换为内存数据写入 buffer.
3. 渲染完成后，将写入数据的 buffer 通过事务的方式提交给 SurfaceFligner，SurfaceFlinger 负责 buffer 的合成显示。

`BLASTBufferQueue` 的初始化过程：

```cpp
new BLASTBufferQueue
    createBufferQueue
        new BufferQueueCore
        new BBQBufferQueueProducer
        new BufferQueueConsumer
    new BLASTBufferItemConsumer
        mCore->mConsumerListener = consumerListener;
```

主要做了如下的工作：
- new 了一个 BufferQueueCore 对象，该对象内部有好几数据结构，用于管理帧缓存
- new 了一个 BBQBufferQueueProducer 对象，该对象用于从 BufferQueueCore 中取出一个 buffer，接着 app 就可以向 buffer 填充要显示的内容
- new 了 BufferQueueConsumer 对象，该对象用于从 BufferQueueCore 中取出一个 buffer，然后提交给 sf 显示

### BufferQueueProducer 获取帧缓存

#### 前置工作

1. 通过生产者设置最大出队列的 Buffer 数目。
2. 给 `BufferQueueCore` 设置一些参数

```cpp
// 获取到 GraphicBuffer 的生产者
sp<IGraphicBufferProducer> igbProducer;
// 返回前面 new 的 BBQBufferQueueProducer
igbProducer = mBlastBufferQueue->getIGraphicBufferProducer();
// 设置最大出队列 buffer 数量
igbProducer->setMaxDequeuedBufferCount(2);
IGraphicBufferProducer::QueueBufferOutput qbOutput;
// 给 BufferQuequCore 设置一些参数
igbProducer->connect(new StubProducerListener, NATIVE_WINDOW_API_CPU, false, &qbOutput);
```

#### 获取 Buffer

1. 初始化一个 fence，fence 是一个指针，是内核的一种硬件同步机制。当 App 拿到 buffer 和 fence 后，就可以调用 GPU 开始绘制，所谓绘制，就是把各种指令转换为需要显示的内存内容并写入 buffer，这个过程通常比较耗时，如果在这里等待就浪费了 cpu 资源，所以程序通知 gpu 开始绘制后（gpu 绘制是一个异步过程），就把 buffer 和 Fence 通过 binder 传递给 Sf 准备合成显示，sf 这个时候其实不知道 gpu 的绘制完成没有，就调用 fence.wait 阻塞等待，当 gpu 完成绘制以后，就会调用 fence.sigal，这个时候 sf 就会从 fence.wait 的阻塞中被唤醒进行后续的 buffer 合成工作。

2. 调用dequeueBuffer， 从 BufferQueueCore 的 mSlots 中获取到一个 buffer 和 一个 fence，准备着给 App 绘制用。

dequeueBuffer() 默认优先从 mFreeBuffers 中获取 slot，因为 mFreeBuffers 中的 slot 已经有 buffer 与之绑定过了，这样就不用再重新分配 buffer 了。然后以 slot 为索引在 mSlot 数组中找到对应的 BufferSlot 对象，并将 BufferSlot 对象的状态从 FREE 修改为 DEQUEUED，然后将 BufferSlot 的索引插入 ActiveBuffers 中，整个过程用动图描述如下如下：

<img src="aosp/display/resources/d_4.gif" style="width:50%"/>

如果 mFreeBuffers 为空，则从 mFreeSlots 中获取 slot：

<img src="aosp/display/resources/d_5.gif" style="width:50%"/>

```cpp
int slot;
sp<Fence> fence;
sp<GraphicBuffer> buf;

// 1. dequeue buffer
igbProducer->dequeueBuffer(&slot, &fence, nativeSurface->width(), nativeSurface->height(),
                                        PIXEL_FORMAT_RGBA_8888, GRALLOC_USAGE_SW_WRITE_OFTEN,
                                        nullptr, nullptr);
igbProducer->requestBuffer(slot, &buf);
```

#### 使用Buffer

App 通过调用 dequeueBuffer 获取到一个可用的 buffer 后，就可以往这个 buffer 中填充数据了. 填充完数据后调用 queueBuffer 把 buffer 再还回去。

```cpp
uint8_t* img = nullptr;
err = buf->lock(GRALLOC_USAGE_SW_WRITE_OFTEN, (void**)(&img));
if (err != NO_ERROR) {
    ALOGE("error: lock failed: %s (%d)", strerror(-err), -err);
    break;
}
int countFrame = 0;
countFrame = (countFrame+1)%3;

fillRGBA8Buffer(img, resolution.getWidth(), resolution.getHeight(), buf->getStride(),
                countFrame == 0 ? 255 : 0,
                countFrame == 1 ? 255 : 0,
                countFrame == 2 ? 255 : 0);
```

`queueBuffer` 的过程中：
- queueBuffer() 根据调用者传入的 slot 参数，将其对应的 BufferSlot 状态从 DEQUEUED 修改为 QUEUED，并根据该 BufferSlot 的信息生成一个 BufferItem 对象，然后添加到 mQueue 队列中。
- 调用 Consumer 的 Listener 监听函数，通知 Consumer 可以调用 acquireBuffer 了。

```cpp
// 3. queue the buffer to display
IGraphicBufferProducer::QueueBufferOutput qbOutput;
IGraphicBufferProducer::QueueBufferInput input(systemTime(), true /* autotimestamp */,
                                                HAL_DATASPACE_UNKNOWN, {},
                                                NATIVE_WINDOW_SCALING_MODE_FREEZE, 0,
                                                Fence::NO_FENCE);
igbProducer->queueBuffer(slot, input, &qbOutput);
```

<img src="aosp/display/resources/d_6.gif" style="width:50%"/>


### BufferQueueProducer 消费帧缓存

acquireBuffer() 从 mQueue 队列中取出 1 个 BufferItem，并作为出参返回给调用者，同时修改该 BufferItem 对应的 slot 状态：QUEUED —> ACQUIRED。

<img src="aosp/display/resources/d_7.gif" style="width:50%"/>

在 `SurfaceFlinger` 拿到 buffer 并消费后，会触发 releaseBuffer(). 根据调用者传入的 slot 参数，将其对应的 BufferSlot 状态从 ACQUIRED 修改为 FREE，并将该 slot 从 mActiveBuffers 中迁移到 mFreeBuffers 中。注意，这里并没有对该 slot 绑定的 buffer 进行任何解绑操作。

<img src="aosp/display/resources/d_8.gif" style="width:50%"/>



## VSync

### 什么是 VSync?

VSync 是一个电平信号，由显示器在屏幕刷新前向外提供，想避免主机视频信息输出与屏幕刷新频率不一致导致的画面撕裂问题。


### Android VSync 基本框架

1. Android 显示器驱动板上有一个 IO 口与主机相连，这个 IO 会定时发送电平信号，触发 VSync 中断。
2. 当 Vsync 信号到来时，linux 内核就会收到一个中断，内核会根据对应的中断号去调用对应的中断处理函数。VSync 的中断处理函数会调用到 DRM 模块中，DRM 模块进一步又会调用到 HWComposor Hal 模块。
3. SurfaceFligner 在初始化时会向 HWComposor HAL 注册一个 Binder 回调（实际就是 sf 这边的一个匿名 Binder），HWComposor HAL 收到硬件 Vsync 信号后就会调用到这个回调，从何将硬件 Vsync 信号发送给 SurfaceFlinger。
4. SurfaceFlinger 中的回调函数收到硬件传递来的 Vsync 信号后，会使用 VsyncSchedule 将 Vsync 信号到达时间和 Vsync 信号周期等信息记录下来。当数据到达 6 个以上时，会通过简单线性回归公式。当 App 需要绘制图像时，Choreographer 通过 binder 向 VsyncSchedule 发起一个请求信号，VsyncSchedule 收到请求后会通过刚才记录的信息计算出`软件 Vsync` 信号，然后通过 socket 将该信号传递给 App，App 收到信号后开始绘制渲染工作。

在 Android 显示系统中，当收到 VSync（垂直同步）信号 后，系统会协调 UI 渲染和帧的绘制，确保画面流畅无撕裂。以下是 Android 收到 VSync 信号后的主要处理流程：

1. VSync 信号的作用
VSync（Vertical Synchronization）信号由显示设备的硬件定时发出（通常是 60Hz，即每 16.67ms 一次），用于同步屏幕刷新和 GPU/CPU 的渲染工作，避免画面撕裂（tearing）和卡顿（jank）。

2. Android 收到 VSync 后的处理流程
Android 的显示系统采用 "VSync 驱动的渲染管线"，主要涉及 Choreographer、SurfaceFlinger 和 RenderThread 等核心组件。具体流程如下：

(1) UI 线程（主线程）处理
Choreographer 接收 VSync 信号：

Choreographer 是 Android 中协调动画、输入和绘制的核心类。

当 VSync 信号到达时，Choreographer 会回调注册的 FrameCallback（如 ViewRootImpl 的 doFrame()）。

执行 UI 更新：

测量（Measure） & 布局（Layout）：如果视图层级有变化（如 View 的尺寸或位置变化），会触发 onMeasure() 和 onLayout()。

绘制（Draw）：调用 View.draw() 生成新的 UI 帧，但此时不会直接渲染到屏幕，而是记录到 DisplayList（GPU 可执行的绘制指令列表）。

(2) RenderThread（渲染线程）处理
同步 DisplayList 到 RenderThread：

UI 线程生成的 DisplayList 会被同步到 RenderThread（独立线程，负责 GPU 渲染）。

RenderThread 负责将 DisplayList 转换为 GPU 可执行的 OpenGL/DrawFrame 操作。

GPU 渲染：

RenderThread 调用 eglSwapBuffers() 提交渲染数据到 GPU。

GPU 执行渲染，生成最终的像素数据（GraphicBuffer）。

(3) SurfaceFlinger 合成
BufferQueue 提交：

渲染完成的 GraphicBuffer 会被放入 BufferQueue（生产者-消费者模型）。

SurfaceFlinger（Android 的合成器）监听 BufferQueue，等待新的帧数据。

合成（Composition）：

SurfaceFlinger 在下一个 VSync 周期内，将所有层的 GraphicBuffer 合成为最终的屏幕图像。

最终通过 Hardware Composer (HWC) 或 GPU 输出到显示设备。


### Choreographer

Choreographer 主要用于负责软件 Vsync 信号的请求与接受。

- App 需要绘制一帧时，Choreographer 负责向 SurfaceFlinger 请求新的软件 Vsync 信号
- 软件 Vsync 信号到达时，Choreographer 负责新的输入、动画、和绘制等任务的执行。


### SurfaceFlinger 图层合成过程

### WMS/AMS 窗口层级结构

WMS/AMS 中使用 WindowContainer 对象来描述一块显示区域，使用 WindowContainer 组成的树来描述整个显示界面。 窗口容器树的每一个节点都是 WindowContainer 的子类。

```java
class WindowContainer{
   /**
     * The parent of this window container.
     * For removing or setting new parent {@link #setParent} should be used, because it also
     * performs configuration updates based on new parent's settings.
     */
    private WindowContainer<WindowContainer> mParent = null;

	// ......

    // List of children for this window container. List is in z-order as the children appear on
    // screen with the top-most window container at the tail of the list.
    protected final WindowList<WindowContainer> mChildren = new WindowList<WindowContainer>();
};
```
#### WindowState 窗口类

在 WMS/AMS 中，一个 WindowState 对象对应一个应用侧的窗口，通常位于树的最底层。可以将屏幕理解为一张画布，WindowState 就是其中的一个图层。


#### WindowToken、ActivityRecord 和 WallpaperWindowToken —— WindowState 的父节点

这三个类可以理解成图层容器类，根据不同的场景作为 WindowState 的父节点。

- Activity 窗口由系统自动创建，不需要 App 主动去调用 ViewManager.addView 去添加一个窗口，比如写一个Activity 或者 Dialog，系统就会在合适的时机为 Activity 或者 Dialog 调用 ViewManager.addView 去向 WindowManager 添加一个窗口。这类 WindowState 在创建的时候，其父节点为 ActivityRecord。

- 非 Activity 窗口，这类窗口需要 App 主动去调用 ViewManager.addView 来添加一个窗口，比如 NavigationBar 窗口的添加，需要 SystemUI 主动去调用 ViewManager.addView 来为 NavigationBar 创建一个新的窗口。这类 WindowState 在创建的时候，其父节点为 WindowToken。

- Activity 之上的窗口，父节点为 WindowToken，如 StatusBar 和 NavigationBar。 Activity 窗口，父节点为 ActivityRecord，如 Launcher。 Activity 之下的窗口，父节点为 WallpaperWindowToken，如 ImageWallpaper 窗口。


#### Task - ActivityRecord 的父节点

一个 Task 对象就代表了一个任务栈，内部保存了一组相同 affinities 属性的相关 Activity，这些 Activity 用于执行一个特定的功能。比如发送短信，拍摄照片等。Taks 继承自 TaskFragment，TaskFragment 继承自 WindowContainer。除了上述的功能，在我们描述的窗口容器树中， Task 是 ActivityRecord 的父节点，内部管理有多个 ActivityRecord 对象。

#### DisplayArea 显示区域

```java
public class DisplayArea<T extends WindowContainer> extends WindowContainer<T> {
    // ......
    private final String mName；
    // ......
}
```


DisplayArea 代表了屏幕上的一块区域。

- DisplayArea 中有一个字符串成员 mName，表示 DisplayArea 对象的名字，其内容由三部分组成 name + ":" + mMinLayer + ":" + mMaxLayer。其中：
    - name：用于指定 DisplayArea 的特殊功能（Feature），如：name 的值为 "WindowedMagnification" 表示 DisplayArea 代表的屏幕区域支持窗口放大。如果没有特殊功能且是叶子节点，name 的值为 "leaf"
    - mMinLayer 和 mMaxLayer，指定当前 DisplayArea 的图层高度范围，WMS 将 Z 轴上的纵向空间分成了 0 到 36 一共 37 个区间，值越大代表图层高度越高，这里两个值，指定了图层高度的范围区间。

下面介绍几种 DisplayArea.

1. WindowedMagnification
    拥有特征的层级： 0-31
    特征描述： 支持窗口缩放的一块区域，一般是通过辅助服务进行缩小或放大

2. HideDisplayCutout
    拥有特征的层级： 0-14 16 18-23 26-31
    特征描述：隐藏剪切区域，即在默认显示设备上隐藏不规则形状的屏幕区域，比如在代码中打开这个功能后，有这个功能的图层就不会延伸到刘海屏区域。

3. OneHanded
    拥有特征的层级：0-23 26-32 34-35
    特征描述：表示支持单手操作的图层

4. FullscreenMagnification
    拥有特征的层级：0-12 15-23 26-27 29-31 33-35
    特征描述：支持全屏幕缩放的图层，和上面的不同，这个是全屏缩放，前面那个可以局部.

5. ImePlaceholder
    拥有特征的层级： 13-14
    特征描述：输入法相关


## 窗口显示过程

> 图层，在 App 里面叫 Window/窗口，在 WMS 叫 SurfaceControl/Surface，在 SurfaceFlinger 叫 Layer。

### 添加窗口方式

Android 中添加一个窗口有两种方式，第一是启动一个 activity，第二种是添加悬浮窗。

### Activity 显示过程整体分析


#### Activity 冷启

冷启动 Activity，目标 App 启动后，会去执行 LaunchActivityItem 和 ResumeActivityItem 这 2 个事务，整体的调用链如下:
> 无论是悬浮窗还是 Activity 最终都会通过 WindowManagerImpl 调用到 WindowManagerGlobal.addView 来添加窗口。
> 其中 WindowManagerGlobal.addView 中核心的三个元素：
> 
> View：窗口对应的 View 树
> ViewGroup.LayoutParams params：窗口的大小位置布局信息
> ViewRootImpl：App 中窗口显示的大管家，会在 WindowManagerGlobal.addView 中构建，和窗口一一对应。


```java
LaunchActivityItem::execute
    ActivityThread::handleLaunchActivity
        ActivityThread::performLaunchActivity
            Instrumentation::newActivity                    -- 构建 Activity
            Activity::attach                                -- 构建 PhoneWindow
                Window::init
                Window::setWindowManager
            Instrumentation::callActivityOnCreate  
                Activity::performCreate
                    Activity::onCreate
                        Activity::setContentView            -- 构建 DecorView

ResumeActivityItem::execute
    ActivityThread::handleResumeActivity
        ActivityThread::performResumeActivity   
            Activity::performResume   
                Instrumentation::callActivityOnResume
                    Activity::onResume        
        WindowManagerImpl::addView                          -- 构建 ViewRootImpl
            WindowManagerGlobal::addView   
                ViewRootImpl::setView                          -- 显示 Window
```

ViewRootImpl::setView 是显示 Activity 的起点，是我们关注的重点，其主要调用链如下：

阶段一：Activity Window DecorView 的初始化

阶段二：向 WMS 添加 Window，预测量 Window 尺寸

阶段三：预测量 View 树，添加 SurfaceControl/Layer，测量 Window 大小，初始化 BLASTBufferQueue

阶段四：View 树的测量布局绘制

阶段五：显示窗口

```java
ViewRootImpl::setView
   ViewRootImpl::requestLayout
      ViewRootImpl::scheduleTraversals             
            ViewRootImpl.TraversalRunnable::run             -- 异步操作 
               ViewRootImpl::doTraversal
                  ViewRootImpl::performTraversals
                    ViewRootImpl::measureHierarchy                  -- 第 3 步预 measure View 树
                    ViewRootImpl::relayoutWindow                    -- 第 4 步：relayoutWindow，添加 SurfaceControl/Layer，测量窗口大小，初始化 BBQ
                        Session::relayout                           -- 远程调用，构建 SurfaceControl，测量窗口大小，Transaction 配置 Layer
                        ViewRootImpl::updateBlastSurfaceIfNeeded    -- 初始化 BBQ              
                    ViewRootImpl::performMeasure                    -- 第 5 步：View 的 测量布局绘制  
                    ViewRootImpl::performLayout
                    ViewRootImpl::performDraw        
                    ViewRootImpl::createSyncIfNeeded                -- 第 6 步：通知 WMS，客户端已经完成绘制，可以显示 Surface 了
   Session.addToDisplayAsUser                           --- 第 1 步：addWindow
   mWindowLayout.computeFrames                          --- 第 2 步：预计算 Window 尺寸
```


<img src="aosp/display/resources/d_9.png" style="width:100%"/>

##### Activity 初始化

1. 获取 WindowManager 服务。
2. 创建 PhoneWindow，并由其管理 DecorView.
3. 获取窗口的布局参数，通过 WindowManager 添加视图(DecorView)。
4. 在 WM 的 addView 过程中，创建 ViewRootImpl， 并通过它进行 addView.


##### 布局过程

1. performTraversals() 方法后的第一个阶段，它会对 View 树进行第一次测量。在此阶段中将会计算出 View 树为显示其内容所需的尺寸，即期望的窗口尺寸。（调用measureHierarchy()）
2. 布局窗口阶段：根据预测量的结果，通过 IWindowSession.relayout() 方法向WMS请求调整窗口的尺寸等属性，这将引发 WMS 对窗口进行重新布局，并将布局结果返回给 ViewRootImpl。（调用relayoutWindow()）
3. 最终测量阶段：预测量的结果是View树所期望的窗口尺寸。然而由于在WMS中影响窗口布局的因素很多，WMS不一定会将窗口准确地布局为View树所要求的尺寸，而迫于WMS作为系统服务的强势地位，View树不得不接受WMS的布局结果。因此在这一阶段，performTraversals()将以窗口的实际尺寸对View树进行最终测量。（调用performMeasure()）
4. 布局View树阶段：完成最终测量之后便可以对View树进行布局了。（调用performLayout()）
5. 绘制阶段：确定了控件的位置与尺寸后，便可以对View树进行绘制了。（调用performDraw()）
6. 显示窗口
