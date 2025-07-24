# MVC、MVP、MVVM

> 本文总阅读量 <span id="busuanzi_value_page_pv"><i class="fa fa-spinner fa-spin"></i></span>次
---

## 远古时代

我们先看下在没有这些概念之前，我们是如何做这种数据、逻辑、视图操作混合项目的，举一个下面的例子，可以看到我们控制逻辑，数据处理以及 UI 操作就是堆起在一起的，这样如果后面某个地方发生变化，例如改变了视图风格或者结构那我们就得到处去修改。按照高内聚的思路，就顺顺当当的提出了 MVC 模式。

```js
<input id="num1">
<input id="num2">
<button onclick="add()">Add</button>
<div id="result"></div>
<script>
function add() {
    // 读取输入
    var n1 = parseInt(document.getElementById('num1').value);
    var n2 = parseInt(document.getElementById('num2').value);
    // 业务逻辑
    var sum = n1 + n2;
    // 显示结果
    document.getElementById('result').innerText = sum;
}
</script>
```

## MVC

MVC 全称是 Model-View-Controller，即“模型-视图-控制器”模式。它是一种分层架构模式，目的是将应用程序的业务逻辑、数据、界面显示和用户输入分离开来，从而提高代码的可维护性、可扩展性和可重用性。

### 模块作用

1. Model

- 职责：管理应用数据，业务逻辑和规则。
- 内容：数据对象、数据库操作、业务处理方法。
- 特点：不关心页面如何显示数据，也不处理用户输入。

2. View

- 职责：负责数据的可视化表现，界面显示。
- 内容：界面布局、按钮文本框、列表等 UI 元素。
- 特点：不直接处理数据和业务逻辑，只负责吧 Model 提供的数据展示给用户。

3. Controller

- 职责：充当 Model 和 View 之间的中介，接收用户输入并调用 Model 或 View 完成相应操作。
- 内容：事件监听、输入处理、调用 Model 更新数据、通知 View 更新界面等。
- 特点：协调 Model 和 View 的交互。

### 问题

MVC 在理论上很好地分离了 Model、View 和 Controller，但在实际开发中，尤其是 Android 这类平台，Activity/Fragment 不可避免地承担了 View 和 Controller 的双重职责，导致代码臃肿、耦合严重、难以维护。为了解决这些现实问题，业界从两个方向演进：一是通过工程架构（如 MVP）进一步分离和解耦 View 与业务逻辑；二是通过底层能力（如数据绑定、响应式流）发展出 MVVM，让 View 和 Model 的同步自动化，进一步提升开发效率和代码质量。

```java
class LoginActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // ...省略
        btnLogin.setOnClickListener {
            val username = etUsername.text.toString()
            val password = etPassword.text.toString()
            val success = UserRepository.login(username, password)
            if (success) {
                showToast("登录成功")
            } else {
                showToast("失败")
            }
        }
    }
}
```


## MVP

MVP的目标： 将视图和控制逻辑之间的耦合通过依赖倒置原则做拆分。

上面 MVC 的案例中可以看出 Activity 兼具 View 的 Controller 的职责，本身没有问题，但是我们在 Activity 中通常会有下面的代码。因为我们很容易拿到 View，所以也就自然而然的直接让 View 与 mode 进行了通信。既然 Activity 在设计上就是 View 的职责，那我们的思路就是把 Controller 的职责拆分出去变成 Presenter。


<img src="android/app/mvc/resources/mvp.png" style="width:100%">

上图可以看出来，在 MVC 的理念下，因为 Activity 的特殊性，往往 V 和 C 耦合在了一起，导致整个 Activity 非常臃肿，最终变成了 VM 或者 CM 模式。

所以为了更好的区分职责，将 Activity 中的 Controller 相关逻辑拆出来成一个 Presenter。 Presenter 其中以 View 操作接口的形式持有了 Activity，以后 Activity 就专注于 View 的工作，至于如何和 Model 通信都交由 Presenter 负责。


下面有一个简单的例子。

```kotlin
// LoginView.kt
interface LoginView {
    fun showLoading()
    fun hideLoading()
    fun showLoginSuccess()
    fun showLoginError(msg: String)
}

// LoginModel.kt
class LoginModel {
    fun checkLogin(username: String, password: String): Boolean {
        return username == "admin" && password == "123456"
    }
}

// LoginPresenter.kt
class LoginPresenter(private val view: LoginView, private val model: LoginModel) {
    fun login(username: String, password: String) {
        view.showLoading()
        val success = model.checkLogin(username, password)
        view.hideLoading()
        if (success) {
            view.showLoginSuccess()
        } else {
            view.showLoginError("用户名或密码错误")
        }
    }
}

// LoginActivity.kt
class LoginActivity : AppCompatActivity(), LoginView {

    private lateinit var presenter: LoginPresenter

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_login)
        presenter = LoginPresenter(this, LoginModel())
        btnLogin.setOnClickListener {
            val username = etUsername.text.toString()
            val password = etPassword.text.toString()
            presenter.login(username, password)
        }
    }

    override fun showLoading() {
    }

    override fun hideLoading() {
    }

    override fun showLoginSuccess() {
        Toast.makeText(this, "登录成功", Toast.LENGTH_SHORT).show()
    }

    override fun showLoginError(msg: String) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
    }
}
```

## MVVM

MVP 是在架构上的优化以让工程逼近 MVC 目标，而 MVVM 是以框架底层能力扩展，尤其是数据绑定（DataBinding）、响应式编程（如 LiveData、RxJava）等底层能力的成熟，MVVM 让 View 和 Model 之间的同步变得自动化，进一步降低了 View 层的复杂度，提升了开发效率。

一般流程如下：

1. View 获取 ViewModel，对其中关键的状态进行观察。
2. View 响应事件后，调用 ViewModel 的接口触发数据获取。
3. ViewModel 通过 Model 进行数据实际操作，获取到数据后，更新自己内部状态。并不需要调用 View 触发视图更新。
4. 状态变化后，会触发View 对应的视图逻辑。

在 Andorid 里面，就是 ViewModel 和 LiveData 的使用。

```kotlin
class LoginStateViewModel : ViewModel(){
    var isLogin = MutableLiveData<Boolean>(MockDataServer.geLoginState())

    fun getLoginState(){
        isLogin.value = MockDataServer.geLoginState()
    }
}

class SettingsActivity: AppCompatActivity() {
    private lateinit var viewModel: LoginStateViewModel

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_settings)

        viewModel = ViewModelProvider(this).get(LoginStateViewModel::class.java)

        viewModel.isLogin.observe(this) { login ->
            // 视图更新逻辑
        }
        findViewById<ImageView>(R.id.sign_in).setOnClickListener {
            getLoginState()
        }
    }

    fun getLoginState(){
        viewModel.getLoginState()
    }
}
```
