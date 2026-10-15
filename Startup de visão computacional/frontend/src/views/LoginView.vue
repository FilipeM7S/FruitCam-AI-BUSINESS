<script setup>
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { login } from "../auth.js";
import { errorText, t } from "../strings.js";
import BackgroundVideo from "../components/BackgroundVideo.vue";
import BrandLogo from "../components/BrandLogo.vue";
import { mediaItem } from "../media.js";
import { vMagnetic } from "../control.js";

const route = useRoute();
const router = useRouter();
const username = ref("");
const password = ref("");
const busy = ref(false);
const message = ref("");
const background = mediaItem("bg-esteira-real");

async function submit() {
  busy.value = true;
  message.value = "";
  try {
    await login(username.value, password.value);
    const next = String(route.query.next || "/");
    router.push(next.startsWith("/") && !next.startsWith("//") ? next : "/");
  } catch (err) {
    message.value = errorText(err);
    password.value = "";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <section class="login">
    <BackgroundVideo id="bg-esteira-real" />
    <div class="login-side">
      <div class="login-brand">
        <BrandLogo :height="96" on="dark" reveal />
        <p class="login-tagline">{{ t.app.tagline }}</p>
      </div>
      <div class="login-card">
        <h1>{{ t.login.title }}</h1>
        <p class="muted">{{ t.login.subtitle }}</p>
        <form class="stack" @submit.prevent="submit" novalidate>
          <label class="field">
            <span>{{ t.login.username }}</span>
            <input v-model.trim="username" name="username" autocomplete="username" autocapitalize="none" required />
          </label>
          <label class="field">
            <span>{{ t.login.password }}</span>
            <input v-model="password" name="password" type="password" autocomplete="current-password" required />
          </label>
          <p v-if="message" class="notice error" role="alert">{{ message }}</p>
          <button v-magnetic class="btn btn-primary btn-block" type="submit" :disabled="busy || !username || !password">
            <span v-if="busy" class="spinner" aria-hidden="true"></span>
            {{ busy ? t.login.submitting : t.login.submit }}
          </button>
        </form>
      </div>
      <RouterLink class="login-how" to="/como-funciona">{{ t.app.navHow }} →</RouterLink>
      <p class="bg-credit">
        <RouterLink class="illustrative" :to="{ path: '/creditos', hash: `#${background.asset}` }">{{ t.media.illustrative }}<span class="visually-hidden">{{ t.media.seeCredits }}</span></RouterLink>
      </p>
    </div>
  </section>
</template>
