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
1. App 调用 dequebuffer 向 BLASTBufferQueue 申请一个 buffer.
2. App 拿到 buffer 后开始渲染，所谓渲染就是把显示指令转换为内存数据写入 buffer.
3. 渲染完成后，将写入数据的 buffer 通过事务的方式提交给 SurfaceFligner，SurfaceFlinger 负责 buffer 的合成显示。
