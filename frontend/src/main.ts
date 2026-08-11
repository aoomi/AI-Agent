import { createApp } from "vue";
import App from "./App.vue";
import {
  appRuntimeKey,
  createAppRuntime,
} from "../../plugins/builtin/short_drama/frontend/app-runtime";
import "../../plugins/builtin/short_drama/frontend/styles.css";

const app = createApp(App);
app.provide(appRuntimeKey, createAppRuntime());
app.mount("#app");
