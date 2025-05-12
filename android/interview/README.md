# Android 面试知识点

--- 

## 四大组件

### Activity

Activity（活动） 是 Android 四大组件之一，代表一个用户交互界面（UI 屏幕），用于展示应用内容并与用户进行交互。每个 Activity 都是一个独立的界面单元，例如：

- 微信的“聊天窗口”是一个 Activity。
- 淘宝的“商品详情页”是另一个 Activity。

#### 生命周期

<img src="android/interview/resources/a_1.png" style="width:70%">

##### 系统部分

当我们点击一个应用图标或者调用 `startActivity` 启动一个新的 `activity` 的时候，framwork 将会创建一个新的 `activity`，大致过程如下: 创建 `activity` 的操作通过 Binder IPC 调用了 AMS(ActivityManagerService) 服务。该服务进行权限以及启动模式的检查后，触发对应的应用创建 `activity`。

##### 应用部分

1. 应用做了基本初始化后，调用 `onCreate` 回调。用户可以在这个回调中做一些初始布局文件的绑定等操作。
2. 随后应用由不可见状态变成可见状态, 调用 `onStart` 函数。此时虽然可见，但是不可交互，处于一种尚未获取焦点的状态。
3. 随后应用获取焦点，变的可交互，此时调用 `onResume` 回调。
4. 如果另外一个 `activity` 启动遮挡了当前 `activity`, 在没有完全遮挡的时候，调用 `onPause` 方法。
5. 如果弹出的 `activity` 没有进一步遮挡，那在弹出的 `activity` 返回后，会调用 `onResume` 方法。进入第三步。
6. 如果进一步的这个 `activity` 被完全遮挡，调用 `onStop` 方法。
7. 调用 `onStop` 方法的页面后续重新进入前台后，会被调用 `onRestart` 方法。进入第二步。
8. 特别需要注意的是，调用 `onPause` 和 `onStop` 的 `activity` 在系统内存不足的时候，有可能会被系统回收，此时如果再返回，会进入第一步。
9. 如果彻底销毁，会调用 `onDestory` 方法。

#### 启动模式

##### standard

对于使用 standard 模式的 `activity`，系统不会在乎这个 `activity` 是否已经在返回栈中存在，每次启动都会创建一个该 `activity` 的新实例。

##### singleTop

当 `activity` 的启动模式指定为 `singleTop`，在启动 `activity` 时如果发现返回栈的栈顶已经是该 `activity`，则认为可以直接使用它，不会再创建新的 `activity` 实例。

##### singleTask

当 `activity` 的启动模式指定为 `singleTask`，每次启动该 `activity` 时，系统首先会在返回栈中检查是否存在该 `activity` 的实例，如果发现已经存在则直接使用该实例，并把在这个 `activity` 之上的所有其他 `activity` 统统出栈，如果没有发现就会创建一个新的 `activity` 实例。

##### singleInstance

<img src="android/interview/resources/a_2.png" style="width:50%">

`activity` 会独占一个全新的任务栈（Task），且该栈中只能存在该 `activity` 的实例。

##### singleInstancePerTask

如果从 不同任务栈 `singleInstancePerTask` 启动同一个  `activity`，每个栈会创建自己的实例。如果 同一任务栈 内再次启动该 Activity，会复用现有实例。主要是为了解决想要创建多个实例的同时又不想被无限创建的情况，即受限多实例。

- 多屏/多窗口: 在分屏或自由窗口模式下，允许同一 Activity 在不同窗口（任务栈）中独立存在。

```kotlin
// 左屏启动
val intentLeft = Intent(this, DetailActivity::class.java).apply {
    flags = Intent.FLAG_ACTIVITY_LAUNCH_ADJACENT // 分屏启动
}
startActivity(intentLeft)

// 右屏启动（会创建另一个实例）
val intentRight = Intent(this, DetailActivity::class.java).apply {
    flags = Intent.FLAG_ACTIVITY_LAUNCH_ADJACENT
}
startActivity(intentRight)
```


#### Fragment

Fragment是一种可以嵌入在Activity当中的UI片段，它能让程序更加合理和充分地利用大屏幕的空间，因而在平板上应用得非常广泛。

##### 设计 Fragment

##### 静态加载

##### 动态加载

### Service

#### Android 线程

#### 生命周期

#### 服务类型

#### Handler 机制

### BroadcastReceiver

#### 动态注册与静态注册

#### 广播类型

#### 发送广播

### ContentProvider

#### 系统 ContentProvider

#### 自定义 ContentProvider

---

## 布局及其常用属性

### 常用的几种布局

#### 线性布局

#### 帧布局

#### 相对布局

#### 约束布局

--- 

## 自定义 View 及 ViewGroup

### 自定义 View

### 自定义 ViewGroup

---

## 动画

### View 动画

#### AlphaAnimation

#### ScaleAnimation

#### TranslateAnimation

#### RotateAnimation

#### AnimationSet

### 属性动画


--- 

## 数据库框架

###  文件流

### SQLite

#### 数据库创建于更新

#### 增删改查

### LitePal 数据库框架


--- 

## 网络框架

### HTTP/HTTPS 基础知识

### OkHttp 网络框架

### Retrofit 网络框架


--- 

## RxJava

### RxJava 的优点

### RxJava 原理

### RxJava 使用

### 操作符

--- 


## 事件分发机制

### 触摸事件分发

### Activity 事件分发

### ViewGroup 与 View 事件分发

--- 


## MVC、MVP、MVVM

### MVC

### MVP

### MVVM


--- 

## 图片加载框架

### Glide

### ImageLoader

### Pocasso


--- 

## 性能优化

### 性能优化

#### 布局优化

#### 绘制优化

#### 内存优化

#### 包优化

#### BitMap 优化


---

## 跨进程通信

### 进程与线程

### Android 的 IPC


--- 

## Java 语言概述


