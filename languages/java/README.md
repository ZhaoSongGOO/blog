# Java

## 数据类型

<img src="languages/java/resources/1.png" style="width:80%">

## Java 类基础

### 访问权限

<img src="languages/java/resources/2.png" style="width:80%">

Java 中访问权限控制级别由小变大的顺序如下：

`private` -> `default`(缺省) -> `protected` -> `public`

1. private

代表私有，仅可用于修饰类的成员​，代表该类的成员只能在本类中被直接访问。

2. default

可用于修饰类或类的成员，当不使用任何访问权限修饰符来声明类或类的成员时，则表示缺省权限修饰符；代表该类或类的成员只能在本类或同一个包的其他类中被直接访问。

3. protected

代表受保护，仅可用于修饰类的成员，被修饰的成员只能在本类，同一个包的所有类，以及其余包的子类可以直接访问。

4. public

代表公共，可用于修饰类或类的成员，这是一个宽松的访问控制级别，代表被修饰的类或成员，可以在任意位置被访问，不管是否在同一个包中或是否具有父子类关系。

## Java 类继承

### 继承的细节

1. 构造方法

- 子类可以在自己的构造方法中通过 super() 调用基类的构造方法。
- 如果子类没有显式调用，默认会调用父类无参数构造方法。
- 如果父类没有无参数构造方法，那就编译失败。

2. 属性重名与静态绑定

如果子类定义了和父类一样的同名属性。遵循的是静态绑定。

```java
class Base{
public int value;
};

class Child extends Base{
public int value;
};

Base b = new Child();
b.value; // 访问 Base 的 value
```

3. 父子类型转换

在 Java 中，下面的写法在编译期会通过，但是运行期会报错。

```java
Base b = new Base();
Child c = (Child)b;
```

4. 可见性重写

重写时，子类方法不能降低父类方法的可见性。不能降低是指，父类如果是public，则子类也必须是public，父类如果是protected，子类可以是protected，也可以是public，即子类可以升级父类方法的可见性但不能降低。

5. 禁止继承

### Java 类继承机制

#### 一个类编码组成部分
- 类变量
- 类初始化代码
    - 定义静态变量的初始化语句
    - 静态初始化代码块
- 类方法
- 实例变量
- 实例初始化代码
    - 定义实例变量的初始化语句
    - 实例初始化代码块
    - 构造方法
- 实例方法
- 父类信息引用

#### 类加载和初始化 

我们在 java 中使用一个类，首先需要进行类加载过程，随后才会进入创建过程生成对应的实例。

类加载过程：
1. 分配内存
2. 给类变量赋初值
3. 设置父子关系
4. 执行类初始化代码
    - 先执行父类的类初始化代码
    - 再执行子类的类初始化代码

创建过程：
1. 分配内存
2. 对实例变量赋默认值
3. 执行实例初始化代码
    - 先执行父类的实例初始化代码
    - 再执行子类的实例初始化代码

```java
package com.uiapp.java_learning;

public  class Shape {
    private int instanceValue = Gen.genValue("Shape instanceValue");

    static private int classValue = Gen.genValue("Shape classValue");

    static {
        System.out.println("Shape static code block");
    }

    {
        System.out.println("Shape instance code block");
    }

    public Shape(){
        System.out.println("Shape constructor");
    }

}

public class Circle extends Shape{
    private int instanceValue = Gen.genValue("Circle instanceValue");

    static private int classValue = Gen.genValue("Circle classValue");

    static {
        System.out.println("Circle static code block");
    }

    {
        System.out.println("Circle instance code block");
    }

    public Circle(){
        super();
        System.out.println("Circle constructor");
    }
}

Circle c = new Circle();
```

```txt
-- 类初始化代码 -- 
Shape classValue
Shape static code block
Circle classValue
Circle static code block
-- 实例初始化代码 --
Shape instanceValue
Shape instance code block
Shape constructor
Circle instanceValue
Circle instance code block
Circle constructor
```

## Java 内部类实现机制

一般而言，内部类与包含它的外部类有比较密切的关系，而与其他类关系不大，定义在类内部，可以实现对外部完全隐藏，可以有更好的封装性，代码实现上也往往更为简洁。不过，内部类只是Java编译器的概念，对于Java虚拟机而言，它是不知道内部类这回事的，每个内部类最后都会被编译为一个独立的类，生成一个独立的字节码文件。

### 静态内部类

如果内部类是外部类的静态成员，那这个内部类就叫做静态内部类。
- 一个静态的内部类和一个普通的独立的类基本没什么区别。
- 静态的内部类唯一的区别在于可以不加外部类限定直接访问外部类的静态成员。
- 静态内部类无法直接访问外部类的非静态成员。

```java
public class Outer1 {
    public static int value;
    public static class Inner{
        public int getValue(){
            return value;
        }
    }
}
```

这个类会被 java 编译成两个 class 文件: `Outer1.class` 和 `Outer1$Inner.class` 其内容分别为

```java
// Outer1.class 
public class Outer1 {
    public static int value;

}

//Outer1$Inner.class
public  class Outer1$Inner{
    public int getValue(){
        return Outer1.value;
    }
}
```

### 成员内部类

与静态内部类不同，除了静态变量和方法，成员内部类还可以直接访问外部类的实例变量和方法。

```java
public class Outer2 {

    public int value;
    class Inner{
        int getValue(){
            return value;
        }
    }
}
```
编译器对其做了如下的处理，生成了 `Outer2.class` 和 `Outer2$Inner.class`

```java
// Outer2.class
public class Outer2 {
    public int value;

    public Outer2() {
    }
}

// Outer2$Inner.class
class Outer2$Inner {
    Outer2$Inner(Outer2 var1) {
        this.this$0 = var1;
    }

    int getValue() {
        return this.this$0.value;
    }
}
```

###  方法内部类

方法内部类是指定义在某个类方法里面的类，如果是定义在静态成员方法中的类，只可以访问外部类静态成员。如果是定义在实例方法中的类，不只是外部类静态成员，实例成员也可以访问。同时两者均可以访问当前方法的 final 参数以及局部变量。


对于这个 static 的方法内部类 编译器对其进行处理:

```java
public class Outer3 {
    private static int value;
    public static void function(final int arg){
        final int local = 0;
        class functionClass1{
            private void show(){
                System.out.println(local + ", " + arg + ", " + value);
            }
        }

        functionClass1 f1 = new functionClass1();
        f1.show();
    }
}
```

```java
// Outer3.class
public class Outer3 {
    private static int value;

    public Outer3() {
    }

    public static void function(final int var0) {
        class functionClass1 {
            functionClass1() {
            }

            private void show() {
                System.out.println("0, " + var0 + ", " + Outer3.value);
            }
        }

        functionClass1 var2 = new functionClass1();
        var2.show();
    }
}
```

对于这个成员方法内部类，处理如下：

```java
public class Outer3 {
    private static int value;
    private int data;
    public void function(final int arg){
        final int local = 0;
        class functionClass1{
            private void show(){
                System.out.println(local + ", " + arg + ", " + value + ", " + data);
            }
        }

        functionClass1 f1 = new functionClass1();
        f1.show();
    }
}
```

```java
// Outer3.class
public class Outer3 {
    private static int value;
    private int data;

    public Outer3() {
    }

    public void function(final int var1) {
        class functionClass1 {
            functionClass1() {
            }

            private void show() {
                System.out.println("0, " + var1 + ", " + Outer3.value + ", " + Outer3.this.data);
            }
        }

        functionClass1 var3 = new functionClass1();
        var3.show();
    }
}
```

### 匿名内部类

匿名内部类只会出现在方法中，，是方法内部类的特殊情况，区别在于其没有名字。

```java
public class Outer4 {
    private int value;
    public void function(final int v){
        Drawable drawable = new Drawable() {
            @Override
            public void draw() {
                System.out.println(v);
                System.out.println(value);
            }
        };
    }
}
```

会被编译器转成两个类,这里有个 access 方法也是编译生成的，主要是因为 value 在 Outer4 中是 private的，你想在一个其余的类访问，那就得提供对应的 publc 接口，所以编译器就默认生成了一个 public 的 static 接口。

```java
// Outer4.class
public class Outer4 {
    private int value;

    public Outer4() {
    }

    public static int access$000(Outer4 o){
        return o.value;
    }
}

//Outer4$1.class
class Outer4$1 implements Drawable {
    Outer4$1(Outer4 var1, int var2) {
        this.this$0 = var1;
        this.val$v = var2;
    }

    public void draw() {
        System.out.println(this.val$v);
        System.out.println(Outer4.access$000(this.this$0)); 
    }
}
```


## Java 接口、抽象类

### 接口

#### 接口基础

- 接口不可以 new 但是可以声明接口类型的变量来承载对象。
- 接口中可以声明变量，但是类型只能是 `public static final`, 可以省略这个标识，因为默认就是。
- 接口可以继承接口，而且可以多继承。
- java8 以后允许在接口中定义静态方法和默认方法以及私有的方法。

```java
public interface Drawable {
    int v = 0;
    private void kernel(){ // 因为私有的，不会对外暴露，所以也就不需要 default，这个只是为了内部复用代码。

    }

    default void draw(){ // public 方法的话，如果想提供默认实现，就得注明 default。

    }

    static void show(){
        System.out.println("Show from Drawable interface");
    }
}
```

### 抽象类

定义了抽象方法的类必须被声明为抽象类，不过，抽象类可以没有抽象方法。抽象类和具体类一样，可以定义具体方法、实例变量等，它和具体类的核心区别是，抽象类不能创建对象(比如，不能使用new Shape())，而具体类可以。

```java
public abstract class Shape {
    //其他代码
    public abstract void draw();
}
```

抽象类和接口之间的关系。

抽象类和接口一般相互配合，一个接口对应一个抽象类，这个抽象类实现了一些默认的接口方法。我们想实现一个接口的时候有如下选择：
- 继承原始接口，实现全部方法。
- 继承抽象类，实现部分方法。


## 泛型类

### 泛型的设计目标与底层原理

假如我们实现了下面的一个泛型类

```java
public class Pair <T, U>{
    public T first;
    public U second;

    public Pair(T t, U u){
        first = t;
        second = u;
    }
}

Pair<String, Integer> p = new Pair<String, Integer>("hello", 12);
String f = p.first;
```
在编译阶段会被转换成下面的逻辑：
- 类型擦除，所以泛型类型均变成 Object 或者限定的上界, 这也就要求所有的泛型参数本身必须是 Object 的子类，int，float 等基础类型肯定不行。
- 类型转换，在代码中增加强制类型转换

```java
public class Pair {
    public Object first;
    public Object second;

    public Pair(Object t, Object u){
        first = t;
        second = u;
    }
}

Pair p = new Pair("hello", 12);
String f = (String)p.first;
```

看起来编译器就是做了原始类型到 Object 以及 Object 到原始类型的转换，那 Java 为什么还要整一个泛型呢？

1. 代码复用，无需多解释，不同的类型可以使用一套逻辑，减少编码量。
2. 提升编码安全性，在多种类型复用一套逻辑的情况下，依然可以在编译期确保类型无误。

### 泛型方法

1. 实例泛型方法可以直接引用类的泛型参数。
2. 实例泛型方法可以定义自己的泛型参数，如果同名就会覆盖类的泛型参数。
3. static 泛型方法无法直接引用类的泛型参数。只能自己自定义

```java
public class Pair <T, U>{
    public T first;
    public U second;

    public Pair(T t, U u){
        first = t;
        second = u;
    }

    public void makePair(T t, U u){
    }

    public <T, U> void makePair2(T t, U u){ // okay, 覆盖类的泛型参数
    }

    public static void do(T t){ // error

    }

    public static <T> void do2(T t){ // okay

    }
}
```

### 泛型接口

```java
public interface Writer<T>{
    void sync(T[] data);
}
```

### 泛型参数限定

1. U 必须是 Number 或者其子类

```java
public class Pair <T , U extends Number>{
    public T first;
    public U second;

    public Pair(T t, U u){
        first = t;
        second = u;
    }

}
```

2. 通配符

`? extends` 实现协变。本身 A 是 B 的父类，但是 Containe<A> 并不是 Container<B> 的父类，即我们无法把一个 Container<B> 对象赋值给 Container<A>。如果允许的话，那我们就可以对 Container<A> 进行操作，将其内容增加 C，其中 C 是 A 的另外一个子类。这样就会导致原本承载 B 的 Container 中塞入了一个不兼容的类型。

但是有时候 Container<B> 对象赋值给 Container<A> 的操作又很方便，所以通配符 ? 就实现了这样的操作。同时为了避免上面提到的转换后修改 Container 的情况，对于 ? 泛型不允许写操作。
例如下面 calc 函数的输入参数 Pair 第二个泛型参数标明其是 U 或者其子类，是一个范围。我们在下面 p.second = second 会失败，因为 我们并不知道 p 的 second 的具体类型。

```java
public class Pair <T , U extends Number>{
    public T first;
    public U second;

    public Pair(T t, U u){
        first = t;
        second = u;
    }

    public void calc(Pair<T, ? extends U> p){ 
        p.second = second; //  error
    }

}
```

`? super` 实现逆变，A 是 B 的父类，我们有时候想要实现 Container<A> 到 Container<B> 的转换，例如下面这样。

```java
public class DynamicArray<E>{
    public void copyTo(DynamicArray<E> dest){
        for(int i=0; i<size; i++){
            dest.add(get(i));
        }
    }
}

DynamicArray<Integer> ints = new DynamicArray<Integer>();
ints.add(100);
ints.add(34);
DynamicArray<Number> numbers = new DynamicArray<Number>();
ints.copyTo(numbers); // 不允许
```

我们想将一个 Integer 类型的数组拷贝到 Number 类型的数组中，这个看起来很合理，但是 Java 不允许，因为 DynamicArray<Number> 类型无法转换到 DynamicArray<Integer>，为什么？首先 从基类类型转换到子类本身就不能直接转换，其次包裹在容器中的转换更加危险，例如下面，允许。

```java

public class Container<E>{
    public E data;

    public E get(Container<E> e){
        return e.data;
    }
}

public class Base{
}

public class ChildA extends Base{
    public void childAFunction(){}
}

public class ChildB extends Base{
    public void childBFunction(){}
}

Container<ChildA> ca = new Container<ChildA>();
Container<Base> cb = new Container<Base>();
cb.data = new ChildB();

ChildA r = ca.get(cb); // 这里假设可以从 Container<Base> 转换到 Container<ChildA>
r.childAFunction(); // error
```

但是为了满足向上面一样的特殊需求，提供了 `? super ` 的操作实现这种转换，同时在这种转换下所有的数据都是可写的，但不可读，为的就是避免将一个不兼容的数据错误返回。

```java
public class Container<E>{
    public E data;

    public E get(Container<? super E> e){
        return e.data; // error, required E, 但是却返回了一个 E 的基类类型。
    }
}
```

### 泛型的限制

1. 基础类型无法作为泛型参数

因为泛型参数擦除后都是 Object，而基础类型不是 Object 的子类。

2. 运行期信息获取

- 无法使用 Container<A>.class 调用，而应直接使用 Contaner.class 
- Container<A>.getClass() 与 Container<B>.getClass() 返回的结果一致，都是 Container。
- `instanceof Container<A>` 也是不允许的，但是支持 `instanceof Container<?>`

3. 类型擦除导致的编译错误

- 擦除类型后是一个方法，没有重载
```java
public static void test(DynamicArray<Integer> intArr)
public static void test(DynamicArray<String> strArr)
```

- 擦除类型后 Child 就实现了同一个接口两次，且参数类型都是 Object。

```java
class Base implements Comparable<Base>{}

class Child extends Base implements Comparable<Child>{

}
```
- 不能通过类型参数创建对象，因为擦除后都是 Object，导致创建的时候没有创建指定类型而是一个 Object 的类型。

```java
T a = new T(); // error
```

- 不能创建泛型数组

为什么呢？在 java 里面，A 是 B 的基类，不同于泛型容器， B[] 可以直接赋值给 A[],这就会出现之前在协变章节提到的数据不安全问题。


## 容器

### 列表和队列

#### ArrayList

类似于 C++ 中的 vector，内部数据连续存储。尾部插入删除复杂度为 O(1), 整体插入删除平均复杂度为 O(n)。

需要注意的是，我们不可以在迭代的过程中直接删除元素。但是在迭代过程中可以使用迭代器删除。

```java
ArrayList<Integer> data = new ArrayList<Integer>();
data.add(1);
data.add(2);
Iterator<Integer> i = data.iterator();
while(i.hasNext()){
    i.next(); // 必须先 next，设置状态
    i.remove();
}
```

#### LinkedList

底层是双向列表，其同时实现了 Queue 和 Deque 接口，可以来当队列、双端队列以及栈来使用。当然如果需要栈，可以直接使用 Stack 容器，这个容器是线程安全的。


### Map 和 Set

#### HashMap

底层基于 HashTable, 数据无序存储。插入查找速率 O(1)。使用 k 计算 hashcode， 存储 <k, v> 到对应 hashcode 的桶下。一个 k 只会存储一份。但是不同的 k 可能会计算得到相同的 hashcode，这就是 hash 碰撞，此时会把这些具有相同 hashcode 的元素以单向链表的形式保存在一个桶下。

#### HashSet

底层基于 HashMap, 数据无序存储，数据无重复。以 元素为 k，固定值为 v，使用 HashMap 去存储。

#### TreeMap

底层基于排序树，数据有序存储。

#### TreeSet

底层基于 TreeMap

#### LinkedHashMap

是 HashMap 的子类，但是其可以确保访问顺序和插入顺序一致。

#### PriorityQueue

底层基于堆，优先级队列。


## 并发

### 线程基础使用

在 java 中线程有两种基础使用方法。

1. 继承 Thread，实现 run 方法。

2. 继承 Runnable 接口，实现 run 方法，进而将这个实现了 run 方法的对象实例作为 Thread 的参数。

### 线程的属性

1. id： 线程具有一个 id 属性，每创建一个新的线程，这 id 都会自增。
2. name：每个线程都有一个名字，我们可以在构造线程的时候或者通过 setName 设置他的名字。
3. 优先级：java 线程总共有 1-10 共 10 个语言级别的优先级(默认为 5)，具体对应系统的优先级则视系统而定，优先级不可靠，只是对系统的建议。
```java
    public final void setPriority(int newPriority)
    public final int getPriority()
```
4. state: 线程有状态，可以通过 getState 接口获取线程状态。

- NEW: 没有调用 start 的线程状态是 NEW。
- TERMINATED:线程运行结束后状态为TERMINATED。
- RUNNABLE: 调用start后线程在执行run方法且没有阻塞时状态为RUNNABLE，不过，RUNNABLE不代表CPU一定在执行该线程的代码，可能正在执行也可能在等待操作系统分配时间片，只是它没有在等待其他条件。
- BLOCKED: 如果一个线程被放置在等待队列，等待锁的时候，就是 BLOCKED 状态。
- WAITING: wait(0), 无限期的 wait，就会进入 waiting 状态。
- TIMED_WAITING: 线程调用 sleep，或者 带有明确时间的 wait();

```java
public enum State {
    NEW,
    RUNNABLE,
    BLOCKED,
    WAITING,
    TIMED_WAITING,
    TERMINATED;
}
```
5. daemon: 前面我们提到，启动线程会启动一条单独的执行流，整个程序只有在所有线程都结束的时候才退出，但daemon线程是例外，当整个程序中剩下的都是daemon线程的时候，程序就会退出。

6. sleep: Thread有一个静态的sleep方法，调用该方法会让当前线程睡眠指定的时间，单位是毫秒。睡眠期间，该线程会让出CPU，但睡眠的时间不一定是确切的给定毫秒数，可能有一定的偏差，偏差与系统定时器和操作系统调度器的准确度和精度有关。睡眠期间，线程可以被中断，如果被中断，sleep会抛出InterruptedException。

7. yield：是一个静态方法，调用该方法，是告诉操作系统的调度器：我现在不着急占用CPU，你可以先让其他线程运行。
8. join：Thread有一个join方法，可以让调用join的线程等待该线程结束。

### 解决数据竞争

#### synchronized

synchronized 可以用来修饰类方法，实例方法以及代码块，其本质就是加锁过程。你可以用任意的一个对象来作为锁，每一个 Object 都持有了一把锁和一个等待队列，synchronized 会先尝试去加锁，加锁成功就执行，失败就把自己放到等待队列里面阻塞。等锁释放后，会在等待队列中随机唤醒一个线程。

当我们使用 synchronized 直接修饰函数的时候，会对锁做隐式使用。
- 对于类方法来说，这个锁就是 类对象。例如 class A 的 类对象是 A.class.
```java
public static synchronized void function(){

}
```
- 对于实例方法，默认是 this。

```java
public synchronized void function(){

}
```
- 对于代码块，则需要我们自己手动指定。

```java
class A///

private Object lock;
public static void function(){
    synchronized(A.class){ // 或者使用 synchronized(lock){} 都可以，任何一个对象都可以做锁。

    }
}
```

其次，synchronized 是可重入的，如果当前线程想要获取一个锁，而这个锁恰好被自己持有，那不会阻塞，而是继续执行，就避免了尝试获取已获取锁的死锁问题。 

### 线程的基本协作机制

每一个 Object 都有两个方法，wait 和 notify 以及一个条件队列。当一个线程调用 wait 方法的时候，就进入阻塞状态，并将当前线程放到这个对象的条件队列中。此时其他线程调用了这个对象的 notify 方法，就会唤醒条件队列中的一个阻塞线程。

- wait/notify方法只能在synchronized代码块内被调用
- wait的具体过程是：
    - 把当前线程放入条件等待队列，释放对象锁，阻塞等待，线程状态变为WAITING或TIMED_WAITING。
    - 等待时间到或被其他线程调用notify/notifyAll从条件队列中移除，这时，要重新竞争对象锁。
        - 如果能够获得锁，线程状态变为RUNNABLE，并从wait调用中返回。
        - 否则，该线程加入对象锁等待队列，线程状态变为BLOCKED，只有在获得锁后才会从wait调用中返回。


### 线程的中断

1. 线程可以使用 interrupt 接口来设置中断状态，但是线程是不是被中断还取决于线程状态和行为。

- RUNNABLE：如果线程在运行中，且没有执行IO操作，interrupt()只是会设置线程的中断标志位，没有任何其他作用。线程应该在运行过程中合适的位置检查中断标志位。
- WAITING/TIMED_WAITING：在这些状态时，对线程对象调用interrupt()会使得该线程抛出InterruptedException。
- BLOCKED: 如果线程在等待锁，对线程对象调用interrupt()只是会设置线程的中断标志位，线程依然会处于BLOCKED状态，也就是说，interrupt()并不能使一个在等待锁的线程真正“中断“。
- TERMINATED/NEW:如果线程尚未启动（NEW）​，或者已经结束（TERMINATED）​，则调用interrupt()对它没有任何效果，中断标志位也不会被设置

## 动态化

### 反射

### 注解

### 动态代理

### 类加载






