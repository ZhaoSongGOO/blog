# HAL (Hardware abostract layer)

> HAL 的作用有两个，第一向上给用户屏蔽了不同硬件设备的差异，第二HAL层是 apache 协议，厂商将自己的硬件相关逻辑放在 HAL 层，可以不开源。如果放在内核中，就需要和内核一块公开源代码了。

## 架构

HAL 在 android 上的发展分成三个阶段：

1.  HAL 阶段 (<8)

在远古阶段，HAL 以 so 包的形式存在，java framwork 通过 jni 来访问。并向上通过 binder 服务的形式服务于应用层。

<img src="aosp/hal/resources/hal_1.png" style="width:50%"/>

2. HIDL + HAL 阶段 (8-10)

这个阶段 HAL 以 binder 服务的形式存在。java framwork 通过 binder 服务调用的方式来访问。并向上通过 binder 服务的形式服务于应用层。

3. AIDL + HAL 阶段 (>11)

这个阶段，应用层不仅可以通过调用通过 binder 服务的方式来访问 HAL，还可以通过 AIDL 好、直接访问。

<img src="aosp/hal/resources/hal_2.png" style="width:50%"/>


## 远古阶段 HAL 调用流程


<img src="aosp/hal/resources/hal_3.png" style="width:100%"/>

1. App 调用 `getSystemService` 函数。
2. 这个函数在基类中实现成调用 `ContextImp` 对象。
3. `ContextImp` 对象调用 SystemServiceRegister 对象，这个对象会注册很多 java 版本的 SystemXXXService 对象。
4. Java 版本的 SystemXXXService 对象 中持有对应的硬件服务代理，这里就是 `IVibratoeService`, 所有的具体操作都是通过这个代理实现的。
5. `IVibratoeService` 与 SystemService 中的对应 Binder 服务 (这里就是 `VivratorService`)通信。
6. Binder 服务通过 jni 调用 hal.so 中的具体能力。

例如，在 `VivratorService` 的jni 如下所示：

```java
public class VibratorService extends IVibratorService.Stub
        implements InputManager.InputDeviceListener {
    // ......
    native static boolean vibratorExists();
    native static void vibratorInit();
    native static void vibratorOn(long milliseconds);
    native static void vibratorOff(); 
    // ......
}
```


### HAL.so 加载过程

> 在 HAL 中，硬件分成两个层次，一个是模块(`hw_module_r`)，一个是设备(`hw_device_t`)，一般一个模块对应一个动态库，每一个模块中包含多个独立的硬件设备。
>
> 1. 模块命名
>
>每一个模块都对应一个动态库，动态库的名称为 `<Module_id>.variant.so`
>
>- MODULE_ID 表示模块的 ID，通常是一个字符串，比如
>
>```c
>// GPS 模块的 MODULE_ID 就是字符串 “gps”
>#define GPS_HARDWARE_MODULE_ID "gps"
>// 振动器模块
>#define VIBRATOR_HARDWARE_MODULE_ID "vibrator"
>```
>
>- variant 可以是 ro.hardware, ro.product.board, ro.board.platform, ro.arch 四个系统属性值之一，系统会依次从属性系统中读取这四个值，如果读取到了，variant 的值就是对应的属性值，就不在读取后面的了。如果四个属性值都不存在，variant 的值为 default。
>
>2. 模块位置
>
>HAL规定了 3 个硬件模块动态共享库的存放路径，定义在 `/hardware/libhardware/hardware.c`
>
>```c
>#if defined(__LP64__)
>#define HAL_LIBRARY_PATH1 "/system/lib64/hw"
>#define HAL_LIBRARY_PATH2 "/vendor/lib64/hw"
>#define HAL_LIBRARY_PATH3 "/odm/lib64/hw"
>#else
>#define HAL_LIBRARY_PATH1 "/system/lib/hw"
>#define HAL_LIBRARY_PATH2 "/vendor/lib/hw"
>#define HAL_LIBRARY_PATH3 "/odm/lib/hw"
>#endif
>```

#### Vibrator HAL 加载分析

1. vibrator init

- Java server 通过 jni 调用 init 方法，在这个方法里面，首先通过 `hw_get_module` 获取模块，在通过  `vibrator_open` 方法获取到对应的设备。模块和设备关联到一个静态的结构体上面，后续可以通过这个结构体来进行访问。

```c
static hw_module_t *gVibraModule = NULL;
static vibrator_device_t *gVibraDevice = NULL;

static void vibratorInit(JNIEnv /* env */, jobject /* clazz */)
{
    if (gVibraModule != NULL) {
        return;
    }

    int err = hw_get_module(VIBRATOR_HARDWARE_MODULE_ID, (hw_module_t const**)&gVibraModule);

    if (err) {
        ALOGE("Couldn't load %s module (%s)", VIBRATOR_HARDWARE_MODULE_ID, strerror(-err));
    } else {
        if (gVibraModule) {
            vibrator_open(gVibraModule, &gVibraDevice);
        }
    }
}
```

## 添加自定义 HAL 服务

[参考资料](http://ahaoframework.tech/006.Hal%E5%BC%80%E5%8F%91%E5%85%A5%E9%97%A8%E4%B8%8E%E5%AE%9E%E8%B7%B5/005.%E4%BC%A0%E7%BB%9F%20Hal%20%E5%BC%80%E5%8F%91%E6%8C%87%E5%8D%974%20%E2%80%94%E2%80%94%20%E5%AE%9E%E7%8E%B0%E4%B8%80%E4%B8%AA%E7%AE%80%E5%8D%95%E7%9A%84%20Hal%20%E6%A8%A1%E5%9D%97.html)



