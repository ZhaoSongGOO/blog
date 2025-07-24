# 安全

## 数据传输安全

### 使用 HTTPS（SSL/TLS）

HTTPS 的数据加密与证书校验机制可以很大程度确保数据通信的安全性。

### 证书校验与证书锁定

信任特定 CA 或服务器证书，而不是系统所有 CA。可以通过 OkHttp、Volley 等主流网络库配置证书锁定。

1. 如何配置证书锁定

OkHttp 等库都提供了对一个的属性，让我们添加证书锁定配置，如果想锁定一个整数一般步骤如下:

- 获取服务器公钥

```bash
echo | openssl s_client -connect example.com:443 | openssl x509 -pubkey -noout | openssl pkey -pubin -outform DER | openssl dgst -sha256 -binary | base64
```

获取证书 -> 解析公钥-> 公钥转成 DER 格式 -> sha256编码 -> base64 编码

- 在 OkHttp 中进行配置

```java
import okhttp3.CertificatePinner;
import okhttp3.OkHttpClient;
CertificatePinner certificatePinner = new CertificatePinner.Builder()
    .add("example.com", "sha256/AbCdEfGhIjKlMnOpQrStUvWxYz1234567890abcdEfG=")
    // 可以添加多个域名和指纹
    .build();
OkHttpClient client = new OkHttpClient.Builder()
    .certificatePinner(certificatePinner)
    .build();
```

### 数据加密（对称/非对称）

对于特别敏感的数据（如支付信息、用户隐私），可以在应用层再加密（如 AES、RSA），即使 HTTPS 被攻破，也能保证数据安全。


1. AES 对称加密

对称加密要求加密和解密使用的 key 一致，下面的代码描述了加密和解密逻辑，需要注意的有下面两点。

- iv 是什么，iv 的存在，可以使得对于一个同样的明文多次加密得到不同的结果。
- 需要注意的是，加密结果是 byte[]. 我们不要直接存储成字符串，会有符号丢失，而是应该先 base64 再存储。

```java
fun aesDecode(value: String): String{
    initSecret()
    val cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
    val ivSpec = IvParameterSpec(iv)
    cipher.init(Cipher.DECRYPT_MODE, aes_key, ivSpec)
    val encryptedBytes = Base64.decode(value) // 先Base64解码
    val decrypted = cipher.doFinal(encryptedBytes)
    return String(decrypted, StandardCharsets.UTF_8)
}

private fun initSecret(){
    if(aes_key == null || iv == null){
        synchronized(this) {
            if(aes_key == null){
                var generator = KeyGenerator.getInstance("AES")
                generator.init(128)
                aes_key = generator.generateKey()
            }
            if(iv == null){
                iv = ByteArray(16) // 16字节IV
                SecureRandom().nextBytes(iv) // 随机生成IV
            }
        }
    }
}

@OptIn(ExperimentalEncodingApi::class)
fun aesEncode(value:String): String {
    initSecret()
    var cipher = Cipher.getInstance("AES/CBC/PKCS5Padding")
    val ivSpec = IvParameterSpec(iv)
    cipher.init(Cipher.ENCRYPT_MODE, aes_key, ivSpec)
    val encrypted: ByteArray? = cipher.doFinal(value.encodeToByteArray())
    return Base64.encode(encrypted!!)
}
```

2. RSA 非对称加密

```java
var publicKey: PublicKey? = null
    var privateKey: PrivateKey? = null

    private fun initRESKey()  {
        if (publicKey == null || privateKey == null)
            {
                synchronized(this) {
                    val keyPairGen = KeyPairGenerator.getInstance("RSA")
                    keyPairGen.initialize(2048) // 推荐 2048 位
                    val keyPair = keyPairGen.generateKeyPair()
                    publicKey = keyPair.public
                    privateKey = keyPair.private
                }
            }
    }

    @OptIn(ExperimentalEncodingApi::class)
    fun resDecode(value: String): String  {
        initRESKey()
        val cipher = Cipher.getInstance("RSA/ECB/PKCS1Padding")
        cipher.init(Cipher.DECRYPT_MODE, privateKey)
        val encryptedBytes = Base64.decode(value) // 先Base64解码
        val decrypted = cipher.doFinal(encryptedBytes)
        return String(decrypted, StandardCharsets.UTF_8)
    }

    @OptIn(ExperimentalEncodingApi::class)
    fun resEncode(value: String): String  {
        initRESKey()
        val cipher = Cipher.getInstance("RSA/ECB/PKCS1Padding")
        cipher.init(Cipher.ENCRYPT_MODE, publicKey)
        val encrypted = cipher.doFinal(value.encodeToByteArray())
        return Base64.encode(encrypted!!)
    }
```

### 接口签名与参数校验

防止请求参数在传输过程中被篡改（如中间人攻击、恶意抓包修改），防止伪造请求（如别人伪造请求调用你的接口），确保数据完整性和来源可信

本质上也是进行加密，下面举个例子。

1. 客户端请求参数

比如要调用 `/pay` 接口，参数如下：
{
  "userId": "12345",
  "amount": "100.00",
  "orderId": "abc123",
  "timestamp": "1710000000"
}

2. 参数约定生成签名

假设双方约定：所有参数按字典序排列后拼接，再加上密钥，用 HMAC-SHA256 算法生成签名。

- 密钥（双方约定好，不能泄露）：`mySecretKey`

签名步骤：

- 按参数名字典序排序：amount=100.00&orderId=abc123&timestamp=1710000000&userId=12345
- 拼接密钥：amount=100.00&orderId=abc123&timestamp=1710000000&userId=12345mySecretKey
- 用 HMAC-SHA256 算法生成签名（假设结果为 `A1B2C3D4E5F6...`）

```json
{
  "userId": "12345",
  "amount": "100.00",
  "orderId": "abc123",
  "timestamp": "1710000000",
  "sign": "A1B2C3D4E5F6..."
}
```

3. 服务端验签流程

- 收到请求后，服务端用同样的方式（同样的密钥、同样的参数顺序）生成签名
- 比较客户端传来的 `sign` 字段和服务器生成的签名是否一致
- 如果一致，说明参数未被篡改，且请求确实来自合法客户端

### Token 机制和身份认证

使用 JWT、OAuth2、Session Token 等方式，确保数据请求来自合法用户，防止伪造和重放攻击。

1. JWT (JSON Web Token)

- 用户登录,用户在 Android App 上输入用户名和密码，发起登录请求。
- 服务端验证身份, 服务端验证用户名和密码正确后，生成一个 JWT（里面包含用户ID、过期时间等信息，并用私钥签名）。
- 客户端保存 JWT, 服务端把 JWT 返回给客户端，客户端（App）本地保存，比如存在 SharedPreferences。
- 后续请求带上 JWT, 客户端每次请求受保护的接口时，在 HTTP Header 里加上 `Authorization: Bearer <JWT>`。
- 服务端校验 JWT, 服务端收到请求后，验证 JWT 的签名和有效期，校验通过就处理业务，否则返回 401 未授权。

优点：
- 无需在服务端保存会话状态（无状态认证）
- 易于扩展，适合分布式系统

2. OAuth2

第三方应用登录（比如用微信/QQ/Google 登录）

- 用户点击“用微信登录”, App 跳转到微信授权页面，用户同意授权。
- 获取授权码, 微信返回一个授权码（code）给 App。
- App 用授权码换取 access_token, App 把 code 发送到自己服务器，服务器再去微信服务器换取 access_token。
- 用 access_token 获取用户信息, 拿着 access_token 可以请求微信 API 获取用户资料。

优点：
- 用户不用把密码给第三方 App，安全性高
- 支持授权粒度控制（比如只授权读取昵称和头像）

3. Session Token

- 用户输入用户名和密码，提交到服务器。
- 服务端验证身份,验证通过后，服务器生成一个 sessionId（如 `abc123xyz`），并在服务端保存该 sessionId 与用户信息的映射。
- 客户端保存 sessionId, 服务器把 sessionId 通过 Cookie 或响应体返回给客户端。
- 后续请求带上 sessionId, 客户端每次请求时自动带上 sessionId（通常通过 Cookie）。
- 服务端校验 sessionId, 服务端查找 sessionId 是否有效，有效就处理业务，否则返回未登录。

优点：
- 实现简单，适合单体应用
- 缺点是服务端要保存所有 session 状态，扩展性有限


### 防止重放攻击

可以为每个请求加时间戳、一次性随机数（nonce），让同一个请求无法被重复利用。

