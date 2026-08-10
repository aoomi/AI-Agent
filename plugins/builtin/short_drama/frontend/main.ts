import { createApp } from "vue";
import App from "./App.vue";
import { appRuntimeKey, createAppRuntime } from "./app-runtime";
import "./styles.css";

const app = createApp(App);
app.provide(appRuntimeKey, createAppRuntime());
app.mount("#app");
