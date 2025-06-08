# APK Build

本文用来分析 Android APK 生成过程的主要流程。

## 主要流程解析

在我们从创建 AS 项目，编写代码，随后点击编译生成 apk，这个过程中 AS 帮我们封装了非常多的细节。我们下面将会进一步去探究这些细节，从而让我们对 Android 应用有一个更全面的认识。

### 准备与初始化

1. 解析 `build.gradle` 文件：
    - 读取项目结构，模块依赖。依赖项：本地库，远程库。
    - Android SDK 版本，构建工具(gradle)版本。
    - 应用属性信息，例如 `applicationId` 等。构建类型及其配置，混淆配置，签名配置。产品 flavor 及其配置。

2. 配置构建任务。
    - 依据 `build.gradle` 的配置，gradle 确定本次构建需要执行的任务以及任务之间的依赖关系，并构建一个任务执行图。

3. 下载依赖
    - 如果项目中使用了远程依赖，将从配置好的远程仓库中下载这些库。

4. 合并清单文件
    - 项目中可能存在多个 AndroidManifest.xml 文件（主模块、库模块、构建变体特定）。Gradle 将它们合并成一个最终的清单文件，用于 APK。

### 编译

1. `AIDL` 编译：
    - 如果项目中有 aidl 文件，那aidl工具会先将这些接口定义编译成 java 接口代码。

2. 资源编译：
> aapt 工具处理 res 目录下所有的资源文件以及 AndroidManifest.xml 文件。
    - 将 xml 文件编译成更紧凑的二进制格式 （*.flat)。
    - 生成 R.java 文件，为每个资源分配一个 ID，使得我们可以在代码中使用 R.xx 来引用资源。
    - 生成资源表(resources.arsc), 包含所有资源的名称 、类型 、配置和 ID 之间的映射关系。

3. java/kotlin 编译
    - Java 编译器 (javac) 编译所有 Java 源代码 (src/main/java, src/<buildType>/java, src/<flavor>/java 等) 以及由 AIDL 和 R.java 生成的 Java 文件。
    - Kotlin 编译器 (kotlinc) 编译所有 Kotlin 源代码 (src/main/kotlin 等)。Kotlin 编译通常与 Java 编译协同工作。
    - 输出是包含标准 Java 字节码的 .class 文件。

4. DEX 编译
> 这是 Android 特有的关键步骤。Android 运行时 (ART/Dalvik) 不直接执行 Java 字节码 (.class 文件)，而是执行 Dalvik Executable (DEX) 格式。
    - d8 编译器（现在是默认）或之前的 dx 工具将编译产生的 .class 文件（包括你项目的、库依赖的、Android SDK 的）转换成一个或多个 .dex 文件。
    - 这个过程还涉及到代码缩减（Shrinking）、优化（Optimization） 和混淆（Obfuscation），通常由 R8 工具完成（R8 整合了 d8 的编译能力和 ProGuard 的缩减/混淆能力，是现在推荐的方式）：
        - 代码缩减: 移除未使用的类、字段、方法和属性（称为 "Tree Shaking"）。
        - 优化: 内联短方法、删除未使用的参数、优化控制流等。
        - 混淆: 将类名、方法名、字段名等重命名为短且无意义的名称（如 a, b, c），增加反编译和逆向工程的难度。
        - 资源缩减: 与代码缩减配合，移除未使用的资源（需要启用 shrinkResources true）。
    - 混淆规则通常在 proguard-rules.pro 文件中定义，库也可能自带自己的规则。
    - 输出是经过优化和混淆（如果启用）的一个或多个 .dex 文件（如 classes.dex, classes2.dex - 对于方法数超过 64K 的应用需要 Multidex）。

5. 原生代码编译

如果项目包含 C/C++ 代码 (JNI)，CMake 或 ndk-build 会被调用来编译生成针对目标 CPU 架构（如 armeabi-v7a, arm64-v8a, x86, x86_64）的共享库（.so 文件）。

### 打包

- 将所有组件打包到一个 APK (Android Package) 文件中：
    - 编译后的 DEX 文件。
    - 编译后的资源文件 (*.flat) 和最终的资源表 (resources.arsc)。
    - 最终的合并清单文件 (AndroidManifest.xml)。
    - 原生库文件 (*.so, 按 ABI 目录存放)。
    - 库依赖项（AAR/JAR 中的资源、原生库等）。
    - assets/ 目录下的原始文件（不会被 aapt2 编译）。
    - libs/ 目录下的 JAR 文件（会被解压并包含其内容）。
        - jar 中的 class 文件会在编译阶段打包进 dex，不会以 class 存储到 apk 中。
        - jar 中的 res 资源会被 aapt 转换。
        - jar 中的 lib、jni、assert 等目录资源会被拷贝到 apk 指定目录中。

本质上，APK 是一个 ZIP 格式的压缩文件，包含了应用运行所需的所有内容。

### 签名/对齐

1. APK 签名 (apksigner / jarsigner):
    - 为什么必须签名？ Android 系统要求所有 APK 在安装前必须使用证书进行数字签名。签名的作用：
        - 身份认证： 标识应用的开发者。
        - 完整性验证： 确保 APK 自签名以来未被篡改。
    - 签名过程：
        - 对于 Debug 构建： Android Studio 会自动使用一个已知的调试密钥库（通常位于 ~/.android/debug.keystore）和证书对 APK 进行签名。这个密钥是公开的，仅用于开发和测试。
        - 对于 Release 构建： 你必须配置 build.gradle 指定你自己的发布密钥库（keystore）及其别名（keyAlias）和密码（keyPassword, storePassword）。Gradle 会使用 apksigner（现代方式）或 jarsigner 工具用你的私钥对 APK 进行签名。妥善保管你的发布密钥库！丢失意味着无法更新应用。
        - 签名信息会被写入 APK 的 META-INF 目录。

2. ZIP 对齐 (zipalign):
    - 目的： 优化 APK 在设备上的内存使用和性能。
    - 原理： 确保 APK 中所有未压缩的文件（如图片、.dex 文件、.so 库）相对于文件开头都按 4 字节边界对齐。
    - 效果： 当系统通过内存映射 (mmap) 访问这些文件时，减少 RAM 消耗并可能加快读取速度。

这个步骤通常在签名之后进行（apksigner 要求输入是已对齐的 APK，所以对齐在签名前做；但 Gradle 流程中 zipalign task 通常配置在 signing task 之前）。

## AAR

上面我们提到了 AS 项目可能依赖了其余模块，而这些模块大多数都是以 AAR 的形式存在。

### 什么是 AAR

全称 `Android Archive`，AAR 本质是一个增强的 Zip 包，专门用于分发和复用 Android 库。它不仅能包含代码，还能包含 Android 特有的资源、清单文件和预编译的本地库等，是 Android 生态中共享功能的标准打包格式。

### 内容

- /AndroidManifest.xml: 库自身的清单文件，声明组件、权限、最低 SDK 等。
- /classes.jar: 核心！ 包含库编译后的 Java/Kotlin 字节码 (.class 文件)。这就是你代码逻辑所在。
- /res/: 包含库的资源文件（布局、字符串、图片、样式等）。这些资源在最终应用构建时会合并。
- /R.txt: 包含库生成的资源 ID 常量定义 (R.java/R.kt 的来源)。
- /assets/: 包含库的原始资源文件（不会被 aapt2 编译）。
- /libs/: 包含库依赖的次级 JAR 文件。
- /jni/ (或 /lib/): 包含库的预编译原生共享库 (.so 文件)，按 ABI 目录组织 (如 armeabi-v7a, arm64-v8a, x86, x86_64)。
- /proguard.txt: 库自带的 ProGuard/R8 混淆规则（如果提供）。
- /public.txt: (可选) 定义库的公共资源（用于严格的资源可见性控制）。
- /lint.jar: (可选) 库自带的 Lint 规则。

### AAR 如何 “分解” 到 APK 中

构建过程 (Gradle + Android Gradle Plugin) 会智能地解压 AAR，提取其各部分内容，并将它们整合到最终的 APK 中，原始 AAR 文件本身不会直接出现在 APK 里。具体分解如下：

1. classes.jar (代码):
处理： 这个 JAR 文件会被提取出来，其中的 .class 文件会和其他依赖库以及你项目的代码一起，送入 DEX 编译器 (d8/r8)。
在 APK 中： 原始 .class 文件消失。库的代码逻辑被编译、优化、混淆（如果启用）后，合并到最终的 classes.dex、classes2.dex 等 DEX 文件中。你无法在 APK 里区分哪些代码来自哪个 AAR 的 classes.jar。

2. /res/ (资源):
处理： res/ 目录下的资源文件会被提取出来。
在 APK 中： 这些资源会和你项目的 res/ 资源以及其他 AAR 库的 res/ 资源一起，被 aapt2 合并、编译和优化。

3. /assets/ (原始资源):
处理： assets/ 目录下的文件会被提取出来。
在 APK 中： 这些文件会被原封不动地复制到最终 APK 的 assets/ 目录下，保持原有的目录结构和文件名。应用通过 AssetManager 访问它们。不同库的 assets/ 内容会叠加在一起，如果文件名和路径相同，后处理的库会覆盖先处理的库（需注意命名冲突）。

4. /jni/ 或 /lib/ (原生共享库 .so):
处理： .so 文件按 ABI 目录提取出来。
在 APK 中： 这些 .so 文件会被直接复制到最终 APK 的 lib/<abi>/ 目录下（例如 lib/arm64-v8a/mylib.so）。它们是预编译好的，构建过程不会修改它们（除非使用 strip 移除调试符号）。最终 APK 的 lib/ 目录会包含所有依赖库和你项目自身的原生库。

5. AndroidManifest.xml (清单文件):
处理： 库的清单文件会被提取出来。
在 APK 中： 这个清单文件会和你项目的清单文件以及其他 AAR 库的清单文件一起，由 Gradle 进行合并 (Manifest Merge)。合并规则基于优先级（通常是 app > libA > libB）和特殊的合并标记（如 tools:replace, tools:remove）。
最终产物： 生成一个最终的、合并好的 AndroidManifest.xml 文件，打包在 APK 的根目录下。库清单中声明的组件（如 Activity, Service, BroadcastReceiver）、权限、<uses-feature> 等会根据合并规则整合进最终清单。

6. 其他文件 (R.txt, proguard.txt, public.txt, lint.jar):
R.txt: 用于在编译时生成库的 R 类，并参与最终的资源 ID 分配。不会出现在 APK 中。
proguard.txt: 库提供的混淆规则会被自动包含到整个项目的 ProGuard/R8 配置中，用于最终的代码优化和混淆。规则本身不会出现在 APK 中。
public.txt: (较少见) 用于控制库资源的可见性（哪些资源可以被应用访问）。构建时使用，不会出现在 APK 中。
lint.jar: 库提供的自定义 Lint 规则，在项目执行 Lint 检查时使用。不会出现在 APK 中。


## 依赖方式

我们可以在 `build.gradle` 中依赖三方库，本节介绍几种依赖方式，并阐述其中的区别和使用场景。

### implementation

<img src="android/interview/build/apk/resources/b_1.png" style="width:10%">

1. 行为
- 依赖项会编译到当前模块中。
- 依赖项的 api 只对当前模块可见。
- 不会将依赖项泄露给编译时依赖当前模块的其他模块。

2. 传递性
- 不传递 API。会阻断依赖项以及依赖项的api依赖的传递。
- 传递实现，依赖项的实现最终会包含在 APK 中。

3. 优点
- 加快构建速度，当 implemention 依赖项发生变化的时候，只有当前模块需要编译，而依赖当前模块的上层模块不需要编译。

### api

<img src="android/interview/build/apk/resources/b_2.png" style="width:30%">

1. 行为
- 依赖项会编译到当前模块中
- 依赖项的 API 会对当前模块和所有在编译时依赖当前模块的其他模块都可见。

2. 传递性
- 传递 API：依赖项及其通过 api 暴露的所有传递依赖，其 API 都会暴露给依赖当前模块的其他模块。
- 传递实现。

3. 缺点
- 构建速度慢。

### CompileOnly

1. 行为
- 依赖项仅在编译时可用。
- 依赖项的代码不会被打包到最终的 APK (或 AAR) 中。
- 依赖项的 API 仅在编译时对当前模块可见。

2. 传递性
- 不传递

3. 目的/优点:
- 减少 APK 大小: 避免将只在编译时需要的库（如注解处理器、代码生成工具、Lombok 等）包含到最终应用中。

### runtimeOnly

1. 行为
- 依赖项只在运行时可用。
- 依赖项的 API 在编译时对当前模块不可见（无法在代码中直接调用其类/方法）。
- 依赖项的代码会被打包到最终的 APK 或者 AAR 中。

2. 传递性
- 无 API 传递。
- 传递实体。

3. 场景
- 相对少见。当你需要在运行时通过反射、动态加载等方式使用一个库，但在编译时不需要（或不能）显式引用它。例如，使用某些插件化框架或热修复库的动态加载部分。


### annotationProcessor / kapt(kotlin注解处理器)

1. 行为
- 指定一个注解处理器库。
- 该库仅在编译时用于处理源代码中的注解。
- 注解处理器本身不会打包到最终 APK 中。
- 注解处理器生成的代码会被编译并包含在 APK 中。

2. 传递性
- 无传递性

## 混淆优化

### 为什么要进行混淆优化？

Android 的混淆优化包括两部分，混淆和优化。两者发生在 class 转换成 Dex 文件期间。

1. 混淆

如果没有混淆，我们的 APK 被解压后，有很多现成的工具可以将 DEX 翻译成可读性非常高的 java/kotlin 代码，这个极大的增加了我们软件的安全风险以及商业价值的泄漏。而采用混淆规则则将一些类名重命名成无意义的字符串，或者单独的字母，极大的增加了反汇编后的理解成本。

2. 优化

优化的主要目的是为了减少应用体积，提高 APP 下载率以及运行时性能。主要的优化措施如下：
- 代码缩减，把一些未被使用到的类从 DEX 中移除。
- 分支逻辑优化，简化控制流。
- 资源缩减。移除未被代码引用到的资源文件。

### mapping.txt 文件

在启用了混淆优化的 APK 构建完成后，会生成一份 mapping.txt 文件。这是一个映射文件，详细的记录了 混淆前的名称 -> 混淆后名称的完整映射关系。至关重要！ 用于将混淆后的崩溃堆栈跟踪信息（StackTrace）还原成可读的原始名称，进行调试。必须妥善保存每个 Release 构建的 mapping.txt！

```txt
    float touchX -> a
    float touchY -> b
    float progress -> c
    int swipeEdge -> d
```


### 如何配置代码混淆规则

1. 在 `build.gradle` 中启用混淆

- minifyEnabled: 总开关。设为 true 即表示启用 R8（或 ProGuard）进行代码缩减、优化和混淆。
- shrinkResources: 启用资源缩减。它会移除未被代码引用的资源。它依赖于 minifyEnabled true 提供的代码引用信息。启用后，未使用的资源（如图片、布局）会被移除。
- proguardFiles: 指定一个或多个混淆规则文件。规则文件告诉 R8/ProGuard 什么代码不能移除（keep）、什么名称不能混淆（keepnames） 以及其他指令。


```groovy
android {
    buildTypes {
        release { // 通常在 release 构建类型中启用
            minifyEnabled true // 核心开关！启用代码缩减、优化和混淆
            shrinkResources true // 启用资源缩减（可选但推荐）
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
            //  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
            //  指定混淆规则文件
        }
        // debug { ... } // debug 通常不启用混淆，方便调试
    }
}
```
2. 基本的混淆规则

```txt
// 保留指定的类/方法/字段不被移除，并且保留它们的名称不被混淆。
-keep public class com.example.MyActivity

// 没有使用则可以移除，如果使用，则不能混淆名称
-keepnames class com.example.PotentiallyReflectedClass
-keep, allowshrinking class com.example.PotentiallyReflectedClass // 等效写法

// -dontwarn 规则： 忽略指定的类或包中存在的编译警告。常用于解决第三方库的警告问题。
-dontwarn okhttp3.**          // 忽略所有 okhttp3 包下的警告
-dontwarn com.somelibrary.**  // 忽略某个库的所有警告
-dontwarn java.lang.invoke.** // 忽略特定包或类的警告

```

3. 资源混淆规则

刚才提到了当设置了 shrinkResources 的时候，会开启资源混淆，如果我们想对混淆过程做一些控制，需要按照如下操作进行。

- 在 res/raw/ 下创建一个 keep.xml 文件（通常路径是 app/src/main/res/raw/keep.xml）。
- 用于指定即使代码中未显式引用，也需要保留的资源。
    - tools:keep: 保留指定资源。
    - tools:discard: 强制移除指定资源（即使代码似乎引用了它，可能是假引用）。
```xml
<?xml version="1.0" encoding="utf-8"?>
<resources xmlns:tools="http://schemas.android.com/tools"
    tools:keep="@layout/used_via_reflection, @drawable/keep_me_always"
    tools:discard="@drawable/unused_but_large_image" />
```

## APK 签名机制

### 签名的作用

1. 身份认证 
- 证明开发者身份：签名使用的数字证书包含开发者信息（组织/个人名称），系统可验证 APK 是否由可信实体发布。
- 防止冒充：恶意应用无法伪造合法开发者的签名，避免“李鬼”应用窃取用户数据。

2. 完整性保护 (Integrity)
- 防篡改：签名相当于 APK 的“数字指纹”。任何对 APK 文件的修改（哪怕 1 字节）都会导致签名验证失败。
- 安全更新：系统只允许相同签名的 APK 覆盖安装，确保更新来自同一开发者。

3. 权限继承
- 相同签名的 APK 可共享数据（如 ContentProvider）、共享进程，甚至声明为同一个应用（android:sharedUserId）。

### 签名工作流程       

#### APK 签名过程

1. 开发者生成非对称密钥对
    - 私钥自己严格保密，用于生成签名。
    - 公钥嵌入证书，随 APK 分发，用来验证签名。

2. 计算摘要
    - 对 APK 所有内容(除签名块本身) 计算 SHA。

3. 生成数字签名
    - 使用私钥对 SHA 进行加密，生成唯一的数字签名。

4. 写入签名信息
    - 将数字签名和公钥写入 APK 的指定位置。

#### 签名验证过程

1. 用户安装 APK
2. 系统提取证书公钥
3. 使用公钥解密签名获得 SHA1
4. 重新计算 APK 的 SHA2
5. 比对 SHA1 是否与 SHA2 相等
    - 相等，安装
    - 不相等，拒绝

### APK 签名实践

1. 生成自己的秘钥

```bash
keytool -genkeypair -v \
  -keystore my-release-key.jks \   # 密钥库文件名
  -keyalg RSA \                    # 算法：RSA/EC
  -keysize 2048 \                  # 密钥长度
  -validity 10000 \                # 有效期（天）
  -alias my-alias \                # 密钥别名
  -storepass 123456 \                # 密钥库密码
  -keypass 123456                    # 私钥密码
```

2. Gradle 配置签名信息

```groovy
    signingConfigs{
        release {
            storeFile file("my-release-key.jks")
            storePassword "123456"  // 从环境变量读取
            keyAlias "my-alias"
            keyPassword "123456"
            v1SigningEnabled true   // 启用 v1
            v2SigningEnabled true   // 启用 v2
        }
    }

    buildTypes {
        release {
            signingConfig signingConfigs.release
        }
    }
```

3. 验证

```bash
# 查看 APK 签名证书
keytool -printcert -jarfile app.apk

# 查看签名方案
apksigner verify -v --print-certs app.apk
```

## flavor 定制

### 在 productFlavors 我们可以定制什么

下面列举了一部分在 `build.gradle` 的 `productFlavors` 块中可配置：

| **属性**                  | **作用**                                                                 | **示例**                                  |
|---------------------------|--------------------------------------------------------------------------|-------------------------------------------|
| `applicationId`           | 独立包名（允许同一设备安装多版本）                                        | `applicationId "com.example.app.paid"`    |
| `versionName` / `versionCode` | 独立版本信息                                                             | `versionName "2.0-pro"`                   |
| `dimension`               | 指定风味维度（多维度组合时必需）                                          | `dimension "tier"`                        |
| `buildConfigField`        | 生成自定义字段到 `BuildConfig.java`                                       | `buildConfigField "String", "API_KEY", '"123"'` |
| `resValue`                | 生成独立资源值（如字符串、颜色）                                          | `resValue "string", "app_name", "Paid App"` |
| `manifestPlaceholders`    | 替换 `AndroidManifest.xml` 中的占位符                                     | `manifestPlaceholders = [appTheme: "@style/PaidTheme"]` |
| `signingConfig`           | 指定签名配置                                                              | `signingConfig signingConfigs.releaseConfig` |
| `minSdkVersion` / `targetSdkVersion` | 覆盖默认 SDK 版本                                                        | `minSdkVersion 23`                        |
| `proguardFiles`           | 独立混淆规则                                                              | `proguardFiles 'paid-proguard-rules.pro'` |
| `matchingFallbacks`       | 解决依赖库缺少匹配风味时的回退策略                                        | `matchingFallbacks = ['free', 'demo']`     |


### sourceSet 在 flavor 的应用

我们可以针对不同的 flavor 设置不同的 sourceSet，以使其编译生成不同的产物。

假设我们现在有这样的一个需求，我们的 apk 包括两种 flavor： free 和 paid。

对于 free 版本的，首页显式 “请升级成测试版本” 字样。

<img src="android/interview/build/apk/resources/b_3.png" style="width:10%">

对于 paid 版本，首页展示正常的 UI。

<img src="android/interview/build/apk/resources/b_4.png" style="width:10%">


1. 创建 paid 和 free 的workspace

- 在 src 目录下新建 free 目录 和 paid 目录，当然，名称无所谓。
- 在各自的工作空间内部创建对应的布局文件和 activity
    - activity 包名和 main 空间一致，这个主要是为了在 AndroidManifest.xml 中可以索引到 Activity。
    - 类名和资源名保持一致

2. 在 `build.gradle` 中配置 sourceSet

```groovy
    sourceSets {
        free {
            res.srcDirs = ['src/free/res']
            java.srcDirs = ['src/free/java']
        }

        paid {
            res.srcDirs = ['src/paid/res']
            java.srcDirs = ['src/paid/java']
        }
    }
```

3. 资源和文件优先级
- 在 Android Gradle 插件里，main 源代码集是默认被所有构建变体包含的，除非你明确地将其排除。所以，main 路径下的资源和代码会自动成为所有构建变体的一部分。
- 假设要构建 free 产品风味
    - 资源的搜索顺序如下：
        - src/free/res（最高优先级）
        - src/main/res（次优先级）
        - 依赖库中的资源（最低优先级）
    - Java 源代码的搜索顺序是：
        - src/free/java
        - src/main/java
        - 依赖库中的类
