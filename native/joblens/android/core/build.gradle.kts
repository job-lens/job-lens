plugins { kotlin("jvm"); kotlin("plugin.serialization") }
java { sourceCompatibility = JavaVersion.VERSION_17; targetCompatibility = JavaVersion.VERSION_17 }
kotlin { compilerOptions { jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17) } }
dependencies {
 implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.8.1")
 implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.10.2")
 testImplementation(kotlin("test"))
 testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.10.2")
}
