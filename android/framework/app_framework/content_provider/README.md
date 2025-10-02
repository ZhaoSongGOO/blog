# Content Provider

在开发 Provider 的时候，我们需要知道其中几个关键的文本标识。

1. URI (Universal Resource Identifier)

URI 是其他应用访问 Provider 的方式，可以视为 Provider 的标识，它的结构如下。

```c
content://${authority}/${path}
```

这里面 `content://` 是固定的 schema 部分，代表是一个 provider 的访问地址。

`authority` 是 provider 注册的时候的标识符，一般我们会在 xml 中进行设置。

```xml
<provider
    // authorities 对应着刚才自定义 ContentProvider 的 authority
    android:authorities="my_authority_name"
    //...
    />
```

`path` 算是 provider 和使用方约定的一个协议，适用方使用某个 path，provider 依据这个 path 去获取对应的数据。

例如下面，我们在 provider 中定义这样一个解析器，第一个解析器会匹配 path 为 `english` 的路径。第二个会匹配 path 为 `english/123` 这种后面跟数字的路径。

```java
private val uriMatcher by lazy {
    val matcher = UriMatcher(UriMatcher.NO_MATCH)
    matcher.addURI(authority, "english", bookDir)
    matcher.addURI(authority, "english/#", bookItem)
    matcher
}
```

2. MIME Type 定义

我们在定义自己的 provider 的时候，需要重写 getType 方法，如下。

```java
override fun getType(uri: Uri) =
    when (uriMatcher.match(uri)) {
        bookDir -> "vnd.android.cursor.dir/vnd.com.uiapp.lion.content.provider.english"
        bookItem -> "vnd.android.cursor.item/vnd.com.uiapp.lion.content.provider.english"
        else -> null
}
```

每一个 URI 所访问的资源都具有一种特定的数据类型，这些数据类型使用多功能 Internet 邮件扩展协议(MIME)来描述。MIME 的定义形式为 "​type/subtype​"​，其中，​type 用来描述数据类型的大类，而 subtype 用来描述数据类型的子类。例如，​"text/html" 描述的数据类型的大类是文本(text)，而子类是超文本标记语言(html)。

Content Provider 组件规定，它所返回的资源的数据类型统一划分为 "vnd.android.cursor.dir" 和 "vnd.android.cursor.item" 两个大类，其中，前者用来描述一个数据集合，后者用来描述一个个体数据。Content Provider 组件所返回的资源的数据类型的子类则是可以自定义的，它的定义形式一般约定为 "vnd.${companyname}.${resourcetype}​"​。

getType 用于哪里呢？`getType` 方法的调用方通常不是你自己的应用，而是Android 系统或其他应用，主要发生在 Intent 解析的场景。

假设另一个应用（比如一个学习软件）想要查看一个 "ID 为 101 的英语单词" 的详细信息。它不知道你的应用存在，但它知道你的 `ContentProvider` 的 `Uri`。它会这样做：

```java
// 在另一个应用中
val wordUri = Uri.parse("content://com.uiapp.lion.content.provider/english/101")

val intent = Intent(Intent.ACTION_VIEW) // 创建一个“查看”意图
intent.setData(wordUri) // 设置要查看的数据 Uri

// 尝试启动能处理这个 Intent 的 Activity
try {
    startActivity(intent)
} catch (e: ActivityNotFoundException) {
    // 没有找到可以处理这个 Uri 的应用
    Toast.makeText(context, "No app can handle this action.", Toast.LENGTH_SHORT).show()
}
```
在这个过程中，Android 系统会执行以下步骤：
1. 系统拿到这个 `intent`，发现它包含一个 `data` (那个 `wordUri`)。
2. 为了找到能够响应这个 `intent` 的 `Activity`，系统需要知道这个 `data` 的确切类型。
3. 因为 schema 是 `content`。于是，系统会通过 `ContentResolver` 调用你 `ContentProvider` 的 `getType(wordUri)` 方法。(期间可能涉及启动 Provider 的逻辑)
4. 你的 `getType` 方法接收到 `wordUri`，匹配后返回 `"vnd.android.cursor.item/vnd.com.uiapp.lion.content.provider.english"`。
5. 现在系统知道了数据类型！它就会去查找所有应用的 `AndroidManifest.xml` 文件，寻找哪个 `Activity` 声明了自己可以处理 (`<action android:name="android.intent.action.VIEW" />`) 这种 MIME 类型 (`<data android:mimeType="..." />`) 的数据。
6. 如果找到了一个匹配的 `Activity`（比如你自己的应用里有一个单词详情页），系统就会启动它，并将 `wordUri` 传递给它。
如果没有 `getType` 方法，或者它返回 `null`，那么上面这套基于数据类型的 Intent 解析机制就完全失效了。


## [ContentProvider 启动过程](android/framework/app_framework/content_provider/content_provider_launch.md)


