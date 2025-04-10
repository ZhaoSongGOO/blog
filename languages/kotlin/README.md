## Kotlin

### 基础知识

#### 声明

- 在声明一个数据的时候，我们要么指定其类型，要么赋初值以自动推导。
- var 声明一个变量
- val 声明一个运行期常量
- const val 声明一个编译器常量

```kotlin
func getValue() :Int{
    return 1;
}

const val gc = getValue(); // error， 编译期无法知道 getValue 的值，而const 要求编译期就可以确定值
const val g = 1; // okay 

fun main(){
    var c:String;
    var b = 12; // Int
    c = "Hello"; 

    val d = false;
    d = true; // error

    const val e = 1; // error, const 不可以修饰局部变量
}

```

#### 函数
1. 声明一个简单的函数

```kotlin
// 指明输入参数类型，指明返回值类型
// 在 kotlin 中，所有的表达式都可以产生值，都可以作为函数的返回值，但是包在一个 block 的表达式无法穿透返回，就像下面一样，我们需要手动 return if 表达式的返回值。
fun max(a: Int, b: Int):Int{
    return if(a > b){
        a
    }else{
        b
    }
}

// 语法糖
fun max(a:Int, b:Int):Int = if(a>b){a}else{b}

// 函数类型参数
// (Int)->String 接收 Int 输入，返回 String 的函数类型。
fun doAction(a:Int, action:(Int)->String):String{
    return action(a);
}

```

#### 区间语法糖

我们有时候想获取一个区间 list，kotlin针对于此提供了一些语法糖。

```kotlin
var a:IntRange = 1..10  // [1, 10]
var b:IntRange = 1 until 10 // [1, 10)
var c: IntProgression = 10 downTo  5 // [10, 9, 8, 7, 6, 5]
```

#### when 语句

类似于 c 的 switch，以及 rust 的 match，kotlin 提供了自己的 when 语句用来进行条件匹配。

需要注意的点：
1. when 的每个匹配条件都是一个可枚举的值，而不是判断条件。
2. 

```kotlin
fun getNext(head:String) :String{
    return when(head){
        "hello" -> "world"
        "bye" -> "friend"
        else -> "unknown"
    }
}
```




