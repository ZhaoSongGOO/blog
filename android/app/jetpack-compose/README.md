# Android 声明式 UI

在 React 等声明式 UI 框架带来的前端新的开发范式的影响下，Android 也开发了自己的声明式框架，就是 Compose。

## Compose 是什么

### API 设计原则

1. 一切皆为函数

Compose 基础是 Composable 函数，这个函数通过多级嵌套形成结构化的函数调用链路，并且经过运行后生成一个 UI 视图树。当数据产生变化时，Composable 调用链会自动执行，从而完成视图更新。

在Compose的世界中，一切组件都是函数，由于没有类的概念，因此不会有任何继承的层次结构，所有组件都是顶层函数。

2. 组合优于继承

Composable 作为函数相互没有继承关系，有利于促使开发者使用组合的视角去思考问题。

3. 单一数据源

Composable 视图的变化只取决于自己输入的单一数据源，确保了数据单向流动。

### Compose 与 View 的关系

<img src="android/app/jetpack-compose/resources/1.png" style="width:80%">

```txt
Android View 树
   |
   |  (ViewGroup/Activity/Fragment)
   |
   └─── ComposeView (View)
            |
            | setContent { ... }
            |
        [Composition]  <--- 管理 Composable 声明式树
            |
            |  Composable 函数（如 Column, Text, Box...）
            |
        [LayoutNode 树]  <--- 每个可见 Composable 对应一个或多个 LayoutNode
            |
            |  实际参与测量、布局、绘制、事件分发
            |
        [最终渲染到屏幕]
```

1. **View**

- Android 的一切 UI 都基于 View 树。
- `ComposeView` 是一个普通的 View，能被加到 ViewGroup、Activity、Fragment 等任何地方。

2. **ComposeView**

- 这是 Compose 的入口 View。
- 你用 `setContent { ... }` 给它设置 Compose 的 UI 内容。

3. **Composition**

- 当你调用 `setContent { ... }` 时，ComposeView 会创建一个 `Composition` 对象。
- Composition 负责管理 Composable 函数的生命周期、重组和状态。
- 它是“声明式 UI 树”的管理者。

4. **Composable**

- 你写的 `Text("Hello")`、`Column { ... }` 等 Composable 函数，都是声明式的 UI 节点。
- 这些节点在 Composition 里管理。

5. **LayoutNode**

- 每个 Composable（只要它有可见 UI）都会在底层生成一个或多个 `LayoutNode`。
- LayoutNode 负责实际的测量、布局、绘制和事件分发。
- LayoutNode 树是 Compose 的“物理 UI 树”，类似于传统的 View 树，但更轻量。

6. **最终渲染**

- LayoutNode 最终会把内容绘制到 ComposeView 的画布上，显示在屏幕上。

需要注意的是，Compose 不是对传统 View 的一个简单包装，而是实现了自己的布局绘制逻辑。

例如 Compose 的 Text 并不会生成 TextView，而是生成 LayoutNode，LayoutNode 实现了 TextView 的显示能力，但不是 View，也不是 TextView。

### Compose 是如何更新的？

1. Compose 的视图更新核心思想

- 声明式 UI：你只描述“现在应该是什么样”，而不是“怎么一步步变成那样”。
- 响应式重组（Recomposition）：当数据（State）变了，Compose 自动重新执行相关 Composable 函数，更新 UI。

2. Compose 的视图更新流程

步骤一：数据驱动

- Compose UI 依赖于 `State`（如 `MutableState`、`remember`、`ViewModel` 等）。
- 当 State 发生变化时，Compose 会自动检测到。

步骤二：标记需要重组的区域

- Compose 记录每个 Composable 函数用到哪些 State。
- 当某个 State 变了，只会标记用到这个 State 的 Composable 需要重组（recompose）。

步骤三：执行重组（Recomposition）

- Compose 并不会全部重绘 UI，而是只重新执行受影响的 Composable 函数。
- 这些函数会生成新的“声明式 UI 结构”，然后和旧的结构做对比。

步骤四：LayoutNode 树的更新

- Compose 会把新的 UI 结构和旧的对比（Diff），只更新有变化的部分。
- 对应的 LayoutNode 只会在必要时被更新、重测量、重绘。

步骤五：局部绘制

- 最终，只有发生变化的 LayoutNode 会走测量、布局和绘制流程。
- 这样就实现了高效的“局部刷新”，而不是全量刷新。

3. 关键机制和原理

State 追踪

- Compose 在每次 Composable 函数执行时，会自动追踪用到的 State。
- State 变化时，Compose 只通知依赖它的 Composable。

Slot Table

- Compose 内部有一个叫 Slot Table 的数据结构，用来高效记录和定位 Composable 的树结构和状态依赖。
- Slot Table 能精确知道哪些 Composable 需要重组，哪些不需要。

Diff & Skip

- Compose 重组时会做 Diff（对比新旧树），能跳过（skip）没有变化的分支，只重组有变化的部分。

LayoutNode 局部更新

- 只有受影响的 LayoutNode 会被标记为“脏”（dirty），才会参与后续的测量、布局和绘制。

4. 例子

```java
@Composable
fun Counter() {
    var count by remember { mutableStateOf(0) }
    Column {
        Text("Count: $count")
        Button(onClick = { count++ }) {
            Text("Add")
        }
    }
}
```
- 只有 `count` 变时，`Text("Count: $count")` 这部分会被重组和重绘，其他部分不会。

5. 总结
- Compose 通过 State 追踪、Slot Table、Diff 算法，实现了精细的、局部的 UI 更新。
- 只有真正依赖发生变化数据的 Composable 和对应的 LayoutNode 会被重组和重绘。
- 这样保证了 Compose UI 的高性能和响应式。

### 如果我们想用的视图，Compose 没有怎么办？

例如 WebView, Compose 没有，我们又必须使用，怎么办？ Compose 提供了一个 AndroidView 组件，其可以用来桥接其余的 View.

<img src="android/app/jetpack-compose/resources/2.png" style="width:40%">


## UI 篇

### Modifier

类似于 XML 中的属性设置，Compose 提供了这个组件属性来链式设置组件样式。

#### Modifier.size

设置组件的大小。

```java
Modifier.size(100.dp)
Modifier.size(width=20.dp, height=30.dp)
```

#### Modifier.background

设置组件背景色。

```java
Modifier.background(Color.Red)  // 纯色

var verticalGradientColor = Brush.verticalGradient(
    colors = listOf(
        Color.Red,
        Color.Blue
    )
)

Modifier.background(verticalGradientColor) // 渐变色
```

#### Modifier.fillMaxSize

尺寸填充。

```java
Modifier.fillMaxSize() // 在宽高上尺寸填充父容器

Modifier.fillMaxWidth() // 宽度填充父容器

Modifier.fillMaxHeight() // 高度填充父容器
```

#### Modifier.border && Modifier.padding

border 用来给组件增加边框，边框可以指定粗细，颜色和形状，padding 可以在边框前后增加间隙，对应的就是内外边距。

```java
Modifier.padding(8.dp) // 外边距
        .border(2.dp, Color.Red, shape = RoundedConrnerShape(2.dp))
        .padding(8.dp)  // 内边距
```



### 基础组件

https://developer.android.com/develop/ui/compose/components?hl=en

### 基础布局

1. 线性布局

Row & Column

2. 帧布局

Box, 类似的还有一个自带很多视觉属性设置的 Surface。

3. 留白，占位

Spacer

4. 约束布局

- 基础使用

```java
@Composable
fun ConstraintTest(){
    ConstraintLayout (
        modifier = Modifier.fillMaxWidth().padding(16.dp).background(color = Color.Blue)
    ){
        val (avatar, username, nickname, followButton) = createRefs()
        Image(
            painter = painterResource(id = R.drawable.robot_8), // 替换成你自己的图片资源
            contentDescription = "User Avatar",
            contentScale = ContentScale.Crop,
            modifier = Modifier
                .size(64.dp)
                .clip(CircleShape)
                // 关联引用并定义约束
                .constrainAs(avatar) {
                    // 约束1：左边缘链接到父容器的左边缘
                    start.linkTo(parent.start)
                    // 约束2：顶部链接到父容器的顶部
                    top.linkTo(parent.top)
                }
        )
        // --- 用户名 (Username) ---
        Text(
            text = "Compose Master",
            style = typography.titleMedium,
            modifier = Modifier.constrainAs(username) {
                // 约束1：左边缘链接到头像的右边缘，并有 16.dp 的间距
                start.linkTo(avatar.end, margin = 16.dp)
                // 约束2：顶部链接到头像的顶部
                top.linkTo(avatar.top)
                // 约束3：右边缘链接到按钮的左边缘，有 8.dp 间距
                end.linkTo(followButton.start, margin = 8.dp)
                // 关键：设置宽度以避免文本过长时超出按钮
                width = Dimension.preferredWrapContent
            }
        )
        // --- 昵称 (Nickname) ---
        Text(
            text = "@jetpack_compose_fan",
            style = typography.bodySmall,
            modifier = Modifier.constrainAs(nickname) {
                // 约束1：左边缘链接到用户名的左边缘 (实现左对齐)
                start.linkTo(username.start)
                // 约束2：顶部链接到用户名的底部，有 4.dp 的间距
                top.linkTo(username.bottom, margin = 4.dp)
            }
        )
        // --- 关注按钮 (Follow Button) ---
        Button(
            onClick = { /*TODO*/ },
            modifier = Modifier.constrainAs(followButton) {
                // 约束1：右边缘链接到父容器的右边缘
                end.linkTo(parent.end)
                // 约束2 & 3：顶部和底部链接到头像的顶部和底部，实现垂直居中
                top.linkTo(avatar.top)
                bottom.linkTo(avatar.bottom)
            }
        ){
            Text("Follow")
        }
    }
}
```

- Guideline 引导线

创建一条看不见的水平或垂直线（可以按 dp 或百分比定位），然后其他组件可以约束到这条线上。非常适合做统一的边距对齐。

```java
val startGuideline = createGuidelineFromStart(16.dp)
// 然后在组件中
// start.linkTo(startGuideline)
```

- Barrier (屏障)
    
创建一个动态的屏障。它的位置由它引用的多个组件中最长或最高的那一个决定。比如，你想让一个按钮始终位于两个不同长度的文本的右边，就可以创建一个 `end` Barrier。

```java
val textBarrier = createEndBarrier(username, nickname)
// 然后在按钮中
// start.linkTo(textBarrier, margin = 16.dp)
```

- Chain (链)

将多个组件在水平或垂直方向上链接在一起，像链条一样。然后可以定义这条“链”的分布方式（`ChainStyle.Spread`, `ChainStyle.SpreadInside`, `ChainStyle.Packed`）。

```java
createHorizontalChain(button1, button2, button3, chainStyle = ChainStyle.Spread)

// `ChainStyle.Spread` (展开) 这是默认的链样式。它会将所有链内元素均匀地分布在可用空间内，包括两端的空间。
// | <--> [  A  ] <--> [  B  ] <--> [  C  ] <--> |

// `ChainStyle.SpreadInside` (内部展开)这个样式会将两端的元素“钉”在链的边界上，然后将剩余的空间均匀地分布在元素之间。
// | [  A  ] <------> [  B  ] <------> [  C  ] |

// `ChainStyle.Packed` (打包/紧凑),这个样式会将所有元素打包在一起，然后将整个组作为一个整体在链的空间内居中。
// | <--------> [ A ]-[ B ]-[ C ] <--------> |

```

- Bias (偏移)

当你同时约束了一个组件的相对两侧（比如 `start` 和 `end`），你可以使用 `horizontalBias` (0f 到 1f) 来控制它在这两者之间的位置。`0.5f` 是居中，`0f` 是靠左，`1f` 是靠右。

```java
start.linkTo(parent.start)
end.linkTo(parent.end)
horizontalBias = 0.25f // 组件会位于左边 1/4 处
```

### Scaffold 脚手架

## 组件数据共享

CompositionLocal 是 Jetpack Compose 中用来在 Composable 层级之间传递数据的一种机制，有点类似于 React 的 Context。它可以让你在 Composable 树中“上层”定义一些值，然后“下层”可以随时获取这些值，而不用一层层参数传递。

通常使用 `compositionLocalOf` 或 `staticCompositionLocalOf`。

- `compositionLocalOf` 用于可变值（比如 theme、user 等）。产生变化只会更新相关的组件，需要做额外的数据记录。
- `staticCompositionLocalOf` 用于不怎么变化的值。产生变化直接触发整个内容的更新，不需要做额外的数据记录。


## 状态管理与重组

组件分为两种，一种是除了参数之外没有任何状态的组件，称为 stateless，另外一种则是持有了某种状态 ，称为 stateful。

在页面更新的时候，对于 stateless 组件，只要输入参数没有变化，那就不进行重组。

在 Compose中 使用 State<T> 描述一个状态，泛型 T 是状态的具体类型。

State<T> 是一个可观察对象。当 Composable 对 State 的 value 进行读取的同时会与 State 建立订阅关系，当 value 发生变化时，作为监听者的 Composable 会自动重组刷新UI。

### 创建状态的方法

```java
// 1. 直接创建

val counter: MutableState<Int> = mutableStateOf(0)

// 2. 结构

val {counter, setCounter} = mutableStateOf(0)

// 3. 代理

var counter by mutableStateOf(0)
```

### 状态持久化

`remember` 是一个用于在 Composable 中保存状态的函数。它的作用是在 Composable 的重组（recomposition）过程中记住某个值，只要 Composable 没有被销毁，这个值就不会丢失。

有时候，更近一步，我们想在 Activity 发生横竖屏切换的时候，确保状态不丢失，就需要使用 `rememberSavable` 这个属性。

### 状态更新引发的重组

这个例子中，点击 Button，会更改 UI。

```java
@Composable
fun CounterDemo() {
    var counter by remember { mutableStateOf(0) }
    MyButtion(counter, onClick = { counter++ })
}
@Composable
fun MyButtion(counter: Int, onClick: () -> Unit) {
    Button(onClick = onClick) {
        Text("点击次数: $counter")
    }
}
```

但是你要这样写，就不会更新了，因为更改的不是状态，而是 MyButton 这个函数的一个局部变量。

```java
@Composable
fun CounterDemo() {
    var counter by remember { mutableStateOf(0) }
    MyButtion(counter)
}
@Composable
fun MyButtion(counter: Int) {
    Button(onClick = { counter++ }) {
        Text("点击次数: $counter")
    }
}
```

### viewModel 状态持久化

### StateHolder

相比于 stateful, stateHolder 将相关的数据统一到一个地方。

例如，传统的写法

```java
@Composable
fun LoginScreen() {
    var username by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    // ... UI 代码
}
```
使用 stateHolder 后。

```java
class LoginStateHolder {
    var username by mutableStateOf("")
    var password by mutableStateOf("")
    fun clear() {
        username = ""
        password = ""
    }
}
@Composable
fun LoginScreen() {
    val state = remember { LoginStateHolder() }
    // ... UI 读取 state.username, state.password
}
```



### 再看重组

经过Compose编译器处理后的Composable代码在对State进行读取的同时，能够自动建立关联，在运行过程中当State变化时，Compose会找到关联的代码块标记为Invalid。在下一渲染帧到来之前，Compose会触发重组并执行invalid代码块，Invalid代码块即下一次重组的范围。能够被标记为Invalid的代码必须是非inline且无返回值的Composable函数或lambda。

State变化影响的代码块，才会参与到重组，不依赖State的代码则不参与重组，这就是重组范围的最小化原则。


### Composable 生命周期

- OnActive（添加到视图树）:即Composable被首次执行，在视图树上创建对应的节点。
- OnUpdate（重组）:Composable跟随重组不断执行，更新视图树上的对应节点。
- onDispose（从视图树移除）：Composable不再被执行，对应节点从视图树上移除。

### 副作用 API
Composable在执行过程中，凡是会影响外界的操作都属于副作用(Side-Effects)，比如弹出Toast、保存本地文件、访问远程或本地数据等。我们已经知道，重组可能会造成Composable频繁反复执行，副作用显然是不应该跟随重组反复执行的。为此，Compose提供了一系列副作用API，可以让副作用API只发生在Composable生命周期的特定阶段，确保行为的可预期性。

1. DisposableEffect


```java
// 进入 Composition 时注册广播，离开时自动注销。
@Composable
fun MyScreen() {
    DisposableEffect(Unit) {
        // 只要 MyScreen 进入 Composition（即被“挂载”到界面上），就执行大括号里的内容。
        val receiver = object : BroadcastReceiver() { ... } 
        val intentFilter = IntentFilter("SOME_ACTION")
        val context = LocalContext.current
        context.registerReceiver(receiver, intentFilter)   
        onDispose {
             // 这是一个“清理”回调。当 MyScreen 离开 Composition（即被销毁、移除、或 key 变化），就会执行这里的内容。
            context.unregisterReceiver(receiver)
        }
    }
}

// 添加和移除回调
@Composable
fun MyScreen() {
    DisposableEffect(Unit) {
        val listener = MyListener()
        myManager.addListener(listener)
        onDispose {
            myManager.removeListener(listener)
        }
    }
}
```

通常用 `Unit` 表示只执行一次（随生命周期），也可以用某个变量作为 key，监听它的变化。

key 变化时，先调用上一次的 `onDispose`，再执行新的 effect。

```java
@Composable
fun MyScreen(userId: String) {
    DisposableEffect(userId) {
        // 每当 userId 变化时，先 onDispose 再重新执行
        val subscription = subscribeToUser(userId)
        onDispose {
            subscription.unsubscribe()
        }
    }
}
```

2. sideEffect

每次重组后执行，无清理逻辑，适合同步外部状态或做一次性同步操作。里面的代码必须是同步的，不能写 suspend 或异步操作。

```java
@Composable
fun MyScreen(isLoggedIn: Boolean) {
    SideEffect {
        Analytics.logScreenView("MyScreen", isLoggedIn)
    }
    // ... UI
}
```

3. launchedEffect

```java
@Composable
fun MyScreen() {
    LaunchedEffect(Unit) {
        // 只在 MyScreen 第一次进入 Composition 时执行
        // 这里可以做网络请求、初始化等
        println("页面加载")
    }
}

@Composable
fun MyScreen(userId: String) {
    LaunchedEffect(userId) {
        // 每当 userId 变化时，自动取消上一个协程，启动新的协程
        val userInfo = getUserInfoFromNetwork(userId)
        // 更新 UI...
    }
}
```


