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

// define a function by arrow
var a = {i:Int ->
    println(i)
    println(i+1)
}

// Define a function with default parameter values

fun say(count:Int = 1, value:String){

}

say(1, "hello")
say(value = "hello")
say(value = "hello", count = 2)

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
```kotlin
fun getNext(head:String) :String{
    return when(head){
        "hello" -> "world"
        "bye" -> "friend"
        else -> "unknown"
    }
}
```

需要注意的点：

1. 带参数的 when 的每个匹配条件是一个可枚举的值，而不是判断条件。不带参数的 when，就可以使用判断条件/表达式

```kotlin
fun getNext(head:String) :String{
    return when(head){
        head != "nihao" -> "world" // error
        "bye" -> "friend"
        else -> "unknown"
    }
}

fun getValue(y: String): String {
    return when {
        y != "hello" -> "is not hello"  // 直接写布尔表达式
        y == "hello" -> "is hello"
        else -> "error" 
    }
}
```
2. 对于无限枚举的值，例如字符串理论上有无限个可能的情况，我们需要增加 else 块. 如果可以枚举完，例如布尔类型以及下面会提到的 sealed (密封类)。

```kotlin
fun getNext(head:boolean) :String{
    return when(head){
        false -> "false"
        true -> "true"
    }
}
```

#### 循环语句

##### for

```kotlin
// 1. interating over a range
for(i in 1..5){

}

// 2. over an array
val numbers = arrayOf(1, 2, 3, 4, 5)
for(n in numbers){

}

// 3. over a collection
val list = listOf("apple", "banana")
for(l in list){

}

```

##### while

```kotlin
val i = 1
while(i < 10){
    i++
}
```

#### Container

```kotlin
    val list = listOf<Int>(1, 2, 3, 4)
    for(i in list){
        println(i)
    }

    val set = setOf<Int>(1, 1, 2, 3, 4)
    for(i in set){
        println(i)
    }

    var map = HashMap<String, Int>()
    map["ZhangSan"] = 12
    map["Lisi"] = 13
    for(i in map){
        println(i.key + ":" + i.value)
    }

    val map2 = mapOf<String, Int>( "Apple" to 12, "Banana" to 13)
    for(i in map2){
        println(i.key + ":" + i.value)
    }
```

#### ```?.``` and ```?:``` and ```!!.```

1. When declaring an ordinary function, the parameters we pass in cannot be null.

```kotlin
fun do(age:Int, name:String){
    // do something
}

do(12, null) // error
```

2. We can lift this restriction by using the "?" symbol. But we must judge the value when it is used inside the function.

```kotlin
fun do(age:Int, name:String?){
    // do something
    println(name.length) // error, name may be null

    if(name != null) {
        println(name.length) // okay
    }
}

do(12, null) // okay
```

3. In order to simplify the above logic, a special operator is provided.

```kotlin
// ?.
a?.b // Check if a is null. If a is null, the expression returns null; otherwise, call b.

// ?:

actiona ?: actionb // if action is null, do action b. otherwise, call action a.

// !!.

a!!.b // Don't check a, just call b.

```

#### let

You just need to check if a is null only once by using the let function.

```kotlin
fun do(p:Person?){
    p?.let {
        p ->
         p.a
         p.b
         p.c
         p.d
    }
}

```

#### block function

The block function is an ordinary function, but we can use it in a cool way.

1. with and run and apply

```kotlin
class Person(name:String, age:Int){
    var name:String = ""
    var age:Int = 0

    init {
        this.name = name
        this.age = age
    }

    fun show() {
        println("Name is " + name + ", age is " + age)
    }
}

val p = Persion("zhaosong", 18)

// You can call the member functions of a Person object within a with block without using the object reference.
with(p) {
    show()
}

// The run block is the same as the with block.
p.run {
    show()
}

// The apply block returns the reference to the object itself.
p.apply {
    show()
}.show()
```

2. custom block function

```kotlin
fun doAction(value:String, block:(String)->Unit):Unit{
    block(value)
}

fun main(){
    doAction("hello"){
        it -> println(it + ", world!")
    }
}
```

#### mutable parameters

```kotlin
fun mutable_args(vararg values:String){
    for(v in values){
        println(v)
    }
}
```

#### infix operation

```kotlin
class Value(val count: Int){
    infix fun equal(value:Value):Boolean{
        return count == value.count
    }
}

infix fun Value.contact(value: Value):String{
    return "$count, ${value.count}"
}


fun chapter8(){
    val v1 = Value(1)
    val v2 = Value(2)
    if(!(v1 equal v2)){
        println("v1 != v2")
    }
    println(v1 contact v2)
}
```

#### inline function

> local return: Local return means using the return statement within a certain code block inside a function (such as a lambda expression, an anonymous function, etc.), causing the program's control flow to exit from this code block and return to the place where this code block was called, rather than exiting from the outer function that contains this code block.

> non-local return : Non-local return refers to using the `return` statement within a code block to directly return from the outer function that contains this code block. 

1. Inline operations are only effective for lambda expressions or anonymous functions passed as parameters to inline functions.

If a function is declared as inline, lambda expressions or anonymous functions passed as its parameters will be inlined automatically at the call site.

```kotlin
fun some(v:String):Unit{
    return
}

inline fun doSome(block:(String)->Unit):Unit{
    block("Hello")
    println("hahahaha")
}

doSome(::some) // cout hahahaha
```

2. If a function is declared as inline, the lambda expression passed as its block - type parameter will also be inlined.

```kotlin
/*
fun doSome():Unit{
    println(hello)
    return
    println("hahahaha") // won't be executed
}
*/

inline fun doSome(block:(String)->Unit):Unit{
    block("Hello")
    println("hahahaha") // won't be executed
}

doSome{
    it ->
        println(it)
        return
}
```

3. local return, Using a local return will only return from the block and will not return from the outer function. 

```kotlin
/*
fun doSome():Unit{
    println("hello")
    println("hahahaha")
}
*/

inline fun doSome(block:(String)->Unit):Unit{
    block("Hello")
    println("hahahaha")
}

doSome{
    it ->
        println(it)
        return@doSome
}

```

4. You can't use non-local return in an non-inline function.
> Kotlin deliberately distinguishes between local returns and non-local returns, and non-inline functions cannot achieve non-local returns.

```kotlin
fun doSome(block:(String)->Unit):String{
    block("Hello")
    println("hahahaha")
    return "Hello"
}

doSome{
    it ->
        println(it)
        return // error, you should use return@doSome
    }
```

5. noinline and crossinline

`noinline` is used to prevent a function-type parameter in an inline function from being inlined. Normally, all function-type parameters of an inline function will be inlined at the call site during compilation. However, when you use `noinline` to modify a parameter, the function corresponding to this parameter will not be inlined. 

```kotlin
inline fun do(noinline block:(Int)->Sting) {} // block will not be inlined
```

Sometimes, we want to pass an inline block to a non-inline higher-order function, which can lead to issues. The reason is that parameters accepted by non-inline higher-order functions do not allow non-local returns, but there might be local returns within an inline block. In this case, we need to use the `crossinline` modifier on the block parameter to ensure that there are no non-local return calls.

```kotlin
inline fun do(crossinline block:(Int)->Sting) {}  

fun noInlineFucntion(block:(String)->Unit){
    block("xixixix")
}

inline fun doSome(crossinline block:(String)->Unit):String{ // forbidden block use non-local return
    noInlineFucntion { 
        it->block(it)
    }
    return "Hello"
}

var c = doSome{
    it ->
    println(it)
    return@doSome
}
```


### 面向对象

#### interface

1. Define an interface

```kotlin
interface Action{
    // The unimplemented methods in the interface must be implemented by the class that implements the interface.
    fun do()
    fun exit()

    // For the methods with default implementations, the classes that inherit the interface can choose to override them
    fun pre(){
        // do something
    }
}
```

2. Implement an interface

```kotlin
// open means this class can be inherited.  By default, classes in Kotlin are final, meaning they cannot be subclassed
open class Person(name:String, age:Int):Actions{
    // data members
    var name:String = ""
    var age:Int = 0
    // primary constructor
    init {
        this.name = name
        this.age = age
    }

    fun speak(){
        println("Person " + this.name + " age:" + this.age)
    }
    
    // sub constructor, if have a primary constructor, must call.
    constructor(name:String):this(name, 0){

    }
    
    // override the function from interface.
    override fun run() {
        println("Person run!")
    }

    override fun sleep() {
        println("Person sleep!")
    }
}

// The Student class inherits from the Person class and needs to call the primary constructor of the parent class.
// Here, it calls the primary constructor through the secondary constructor of the parent class.
class Student(name:String, age:Int): Person(name){}
```

#### data class

In korlin, a data class is a special type of class that is mainly designed to hold data. It comes with several useful features,
which greatly simplify the process of creating class for data storage.

1. A data class generates some methods automatically.
2. A data class must have at least one primary constructor parameter.
3. Primary ctr parameters must be marked as val or var.
4. Data classes cannot be abstract, open, sealed, or inner.

```kotlin
data class Person(val name: String, var age: Int){
    fun show(){
        // do something
    }
}

fun main() {
    // Create an instance of the Person data class
    val person1 = Person("Alice", 25)
    val person2 = Person("Alice", 25)

    // Using the automatically generated toString() method
    println(person1) 

    // Using the automatically generated equals() method
    println(person1 == person2) 

    // Using the copy() method
    val person3 = person1.copy(age = 26)
    println(person3)
}
```

#### Singleton class

By initializing a class with the object keyword, you can obtain a singleton class. You cannot provide a constructor for it. You can call its methods in the form of ClassName.methodName.

```kotlin
object SingletonClass{
    fun hello(){
        // do someting
    }
}

SingletonClass.hello()

```

#### companion object

In kotlin, we can define a static function by companion object. Kotlin can ensure that a companion object is reused among all the objects of the same class. 

```kotlin
class StaticFunctionDemo {
    companion object {
        fun static_function(){
            println("This is a static function!")
        }
    }
}
```

#### lateinit

```kotlin
class Kernel(version:String){
    var version :String // error,
}
```
For ordinary classes, properties must be initialized. How to solve this problem?
- ```var version: String? = null```
- ```var version: String = ""```
- ```lateinit var version: String ```

#### class delegate

```kotlin
interface InteractiveComponent{
    fun onClick()
    fun onDrag()
}

class ViewComponent:InteractiveComponent{
    override fun onClick() {
        println("onClick trigger")
    }

    override fun onDrag() {
        println("onDrag trigger")
    }
}

class WindowComponent:InteractiveComponent by ViewComponent() {}
```

#### properties delegate

```kotlin
class PropDelegate{
    operator fun setValue(myClass:PropDelegateDemo, props: KProperty<*>, value: String){
        println("setValue $value")
    }
    operator fun getValue(myClass:PropDelegateDemo, props: KProperty<*>):String{
        println("getValue")
        return "Hello"
    }
}

class Later<T>(val block: () -> T) {
    var value: Any? = null
    operator fun getValue(any: Any?, prop: KProperty<*>): T {
        if (value == null) {
            value = block()
        }
        return value as T
    }
}

class PropDelegateDemo{
    var p by PropDelegate()
    val lazyV by Later<String>{
        println("lazy GetValue")
        "lazy nihao"
    }
}
```


#### sealed class

The purpose of a sealed class is to create a complete enumeration space.

1. A sealed class is an abstract class.
2. Its subclasses should be in the same file as the sealed class.

```kotlin
sealed class Result

data class Success(val data: String) : Result()
data class Error(val message: String) : Result()

fun handleResult(result: Result): String {
    return when (result) {
        is Success -> "Success: ${result.data}"
        is Error -> "Error: ${result.message}"
    }
}

fun main() {
    val successResult = Success("Data fetched successfully")
    val errorResult = Error("Network error")

    println(handleResult(successResult))
    println(handleResult(errorResult))
}
```

#### extension function

You can dynamically add a function to a class.

```kotlin
fun Person.run(){

}

```

#### operation override

```kotlin
class Money(count:Int){
    var count:Int = 0
    init {
        this.count = count
    }
    operator fun plus(count: Int):Money{
        val c = this.count + count
        return Money(c)
    }

    operator fun plus(money: Money):Money{
        val c = this.count + money.count
        return Money(c)
    }
}
```

### Generic programming

#### Generic function

```kotlin
fun <K, V> printPair(key: K, value: V) {
    println("Key: $key, Value: $value")
}

fun main() {
    printPair("Name", "John")
    printPair(1, "One")
}
```

#### Generic class

```kotlin
class All<T>{
    fun print(v:T){
        println(v)
    }
}
```

#### Generic member function

```kotlin
class All2{
    fun <T> print(v:T){
        println(v)
    }
}
```

#### Generic type bounds

```kotlin
class All3{
    fun <T:Number> print_number(v:T){
        println(v)
    }
}
```

#### Covariance

协变就是当 B 继承 于 A 的时候，我们不止可以把 B 的引用赋值给 A，同时 template<B> 也可以赋值给 template<A>。

首先想一下，为什么在 C++ 中不允许，例如 vector<B> 不能赋值给 vector<A>，因为当我们把包含B的容器赋值给基类类型容器后，意味着类型限制变宽松。那我们拿到vector<A>的时候，就可以使用A的另外一个子类C来做替换，这会在返回的时候出现异常，因为原来的 vector<B> 中有了一个非 B 的数据类型。
从上面的描述可以看出来，出现问题的原因是 ”用户可能存在对 vector<A> 的写操作“。
因此 Kotlin 中提供了一些关键字，如果你使用这些关键字修饰你的方法，确保其拿到弱限制容器后不对其做写操作，就允许这种行为，这就是协变。

```kotlin
open class Base(val name:String="base"){
    open fun say(){
        println("Base say")
    }
}

class Child:Base("child"){
    override fun say(){
        println("Child say")
    }
}

class Child2:Base("Child1"){
    override fun say(){
        println("Child2 say")
    }
}

// out 代表我不会接受一个同样类型的参数作为函数输入
class SimpleData<out T>(val data:T){

    // 如果不必须传入一个 T 类型的输入参数，那就使用 @UnsafeVariance
    fun print(value:@UnsafeVariance T){
        println("bababa")
    }
}

fun dataHandler(data:SimpleData<Base>){
    data.data.say()
}

fun testCovariance(){
    val d = SimpleData<Child>(Child())
    // 这里本应报错，因为 虽然Child是Base的子类，但是 Simple<Child> 并不是 Simple<Base> 的子类
    // 但是因为使用了协变， out关键字表明 在Simple包裹下，内部的T参数不会被修改，在只读的背景下，就可以赋值。
    dataHandler(d)
    d.data
}
```

#### Contravariance

什么是逆变，依旧 B 继承 A，Kotlin 中允许把 template<A> 传递给 template<B>, 这在 C++ 中是不可能的，甚至直接违反了继承关系。

为什么需要逆变？在某些时候可能处理子类的方法对于基类也适用。

为什么会有安全问题？ 因为当我们把基类容器转换成子类容器，意味着我们拿到了一个更严格的类型容器，那我们从这个容器中去除对应的类型的时候，预期是严格类型 B， 但是实际上返回的是A，就会有运行期报错。

<img src="languages/kotlin/resources/1.png" height="100" />

```kotlin
open class Base{

}

class Child:Base(){

}

// 使用 in 关键字，标明这个容器不支持内部数据的读操作。
interface Transform<in T>{
    fun transform():@UnsafeVariance T // 必须要有的话，UnsafeVariance 标注
}

fun handleTransformer(trans: Transform<Child>){
    val re = trans.transform() // 因为 trans的类型，推导出re是Child类型的，但是transform 返回Base类型, 这里直接触发异常
}


var trans = object :Transform<Base> {
    override fun transform(): Base {
        return Base()
    }

}
```



### Coroutine

#### 什么是协程？

协程是一种更加高效的线程资源使用方式，在我们往常的多线程开发环境下，如果我们一个线程在做 IO 操作，在我们没有使用阻塞 IO 主动放弃 CPU 竞争的时候，我们需要轮询等待 IO 返回。
此时线程没有做任何的处理，但是仍然参数 CPU 竞争。如果有协程，我们可以在这个线程中把这个轮询操作变成一个协程，在其发起 IO 请求的时候主动放弃协程调度，转而去执行其他逻辑，此时我们的线程仍然在做真正的计算工作，而不是空转。

所以关键点是如何定义一个协程以及协程在什么时候会让出调度。

#### 协程调度策略

刚才提到，协程是一个一组运行在同一个线程上的调度行为，难道我们在一个线程创建的协程都只会运行在这一个线程吗？不是的，至少Kotlin中提供了多种调度策略，依据不同的调度策略，协程将会运行在同一个线程，或者交给线程池去运行。甚至同一个线程上的两个协程都会被不同的线程来执行。


| 调度器类型       | 线程策略           | 适用场景          |
|------| ------|------|
| Dispatchers.Main| 单线程（UI线程）   | Android UI更新    |
| Dispatchers.Default | 固定大小线程池   | CPU密集型计算     |
| Dispatchers.IO  | 弹性线程池         | IO阻塞操作        |
| Dispatchers.Unconfined | 无约束(默认首次在当前线程调度)      | 测试/特殊场景     |

如何配置调度策略?

在创建协程的时候，launch 提供参数让我们配置具体的 Dispatchers，默认是 Default。

#### 协程的层级关系

和线程的区别之一是协程是一个树状结构，而不是扁平的。当我们在一个协程中创建另一个协程，那新创建的协程将会是当前协程的子协程。
树根的协程称为顶层协程。


#### 如何创建一个协程？

先总结回答:
- GlobalScope 和 runningBlock 可以在任何地方调用
- CoroutineScope 只可以在协程作用域或者挂起函数中调用
- launch 只能在协程作用域中调用
- 

1. GlobalScope + launch

启动一个全局协程作用域，其中直接创建的所有的子协程都是顶层协程。

```kotlin
GlobalScope.launch {
    launch {
        printThreadName("1")
    }

    launch {
        printThreadName("2")
    }
}
```

2. runBlocking 

- 在其内部创建的协程都叫做子协程。
- runBlocking 会阻塞当前线程，知道其内部所有内容以及子协程执行完成。

```kotlin
runBlocking {
    launch {
        printThreadName("1")
    }

    launch {
        printThreadName("2")
    }
}
```

3. CoroutineScope

其会在内部所有协程执行完成之间，阻塞外部携程
```kotlin
    runBlocking {
        coroutineScope {
            launch(Dispatchers.IO) {
                for (i in 1..10) {
                    printThreadName("$i")
                    delay(1000)
                }
            }
        }
        println("coroutineScope finished") // 内部执行完成后才会输出
    }
    println("runBlocking finished")
```

4. 自定义 Scope + Job

- 使用自己创建的 Scope, launch 后不会阻塞当前线程。
- 你可以手动 cancel 掉所有的任务。

```kotlin
var j = Job()
var scope = CoroutineScope(j)
scope.launch {
    launch{
        printThreadName("1")

    }

    launch{
        printThreadName("2")
    }

    launch{
        printThreadName("3")
    }
}

j.cancel()
Thread.sleep(1000)
```

5. async 和 await 获取协程执行结果。

- async 只可以在协程作用域中调用
- async 会创建一个子协程，同时返回一个 Deferred<T> 类型。
- 对 Deferred<T> 调用 await 阻塞当前携程，等待结果。

```kotlin
launch{
    var r = async {
        1 + 2
    }

    println(r.await()) // 会阻塞 launch 发起的协程，等待 async 协程返回数据。
}
```

6. withContext 简化

withCntext 类似于 async + await，其会创建新协程执行逻辑，并阻塞当前协程以等待返回结果。

```kotlin
fun main() {
    runBlocking {
        val result = withContext(Dispatchers.Default) {
            5 + 5
        }
        println(result)
    }
}
```

#### 如何让出调度？

刚才我们也提到了，协程的调度基础是每个协程需要主动让出以调度其余的协程，如果我们有一个协程一直在死循环，那将永远不会实现调度以及并发。

一般协程要让出自己的执行权，可以通过调用挂起函数来实现。

##### 如何使用挂起函数

delay 就是一个挂起函数，我们可以看下如下的代码，我在三个地方进行断点，按照断点可以看到执行逻辑。

<img src="languages/kotlin/resources/5.png" height="200" />

1. 协程1被调度，执行到delay，让出自己的调度权

<img src="languages/kotlin/resources/2.png" height="200" />

2. 1让出后，协程2被调度，运行完成，让出调度权

<img src="languages/kotlin/resources/3.png" height="200" />

3. 协程1恢复调度，从恢复点继续执行

<img src="languages/kotlin/resources/4.png" height="200" />


```kotlin
var j = Job()
var scope = CoroutineScope(j)
scope.launch {
    launch{
        delay(100)
        printThreadName("1")

    }

    launch{
        printThreadName("2")
    }

}
```
##### 如何定义自己的挂起函数

- 使用 `suspend` 关键字定义挂起函数，挂起函数可以互相调用。
- 挂起函数只可以被其他挂起函数或者在协程作用域内调用。
- 挂起函数并不具备协程作用域，其内部无法使用 launch 开新的协程。
- 可以使用 coroutineScope 包裹以使得挂起函数内部可以使用 launch.

```kotlin
suspend fun mySuspend(){
    delay(100) // 调用其他挂起函数
    coroutineScope { 
        launch{
            //...
        }
    }
}
```

#### 协程实战

实现一个异步的网络库。

```kotlin
interface NetworkCallback {
    fun onSuccess(data: String)
    fun onError(error: Throwable)
}

object NetworkHelper {
    
    suspend fun fetchData(url: String): String {
        return withContext(Dispatchers.IO) { // 阻塞当前协程，执行内部逻辑，执行完成后返回。
            delay(1000) // 挂起，放弃调度，但是在 withContext 这个作用域内只有自己一个任务，又被重新触发
            if (url.isEmpty()) throw IllegalArgumentException("Invalid URL")
            "Data from $url"
        }
    }

    // 支持回调的封装
    fun fetchWithCallback(
        url: String,
        callback: NetworkCallback,
        scope: CoroutineScope = CoroutineScope(Dispatchers.IO)
    ) {
        scope.launch {
            try {
                val result = fetchData(url) // 调用挂起函数，放弃调度，但是当前协程中只有自己一个任务，又被重新触发。
                callback.onSuccess(result)
            } catch (e: Exception) {
                callback.onError(e)
            }
        }
    }

    // 另一种回调风格
    fun <T> executeAsync(
        block: suspend () -> T,
        onSuccess: (T) -> Unit,
        onError: (Throwable) -> Unit = { it.printStackTrace() },
        scope: CoroutineScope = CoroutineScope(Dispatchers.Main)
    ) {
        scope.launch {
            try {
                val result = block()
                onSuccess(result)
            } catch (e: Exception) {
                onError(e)
            }
        }
    }
}

fun main(){
    NetworkHelper.fetchWithCallback(
        url = "https://api.example.com/data",
        callback = object : NetworkCallback {
            override fun onSuccess(data: String) {
                println("Success: $data")
            }
            override fun onError(error: Throwable) {
                println("Error: ${error.message}")
            }
        }
    )

    Thread.sleep(2000)
}
```