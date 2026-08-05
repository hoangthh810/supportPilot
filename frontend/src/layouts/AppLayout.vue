<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink class="brand" to="/">SupportPilot</RouterLink>
      <span class="environment-label">Support workspace</span>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 64px;
  padding: 0 32px;
  color: #fff;
  background: #172033;
}

.brand {
  font-size: 1.125rem;
  font-weight: 700;
  text-decoration: none;
}

.environment-label {
  color: #cbd5e1;
  font-size: 0.875rem;
}

.app-main {
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
  padding: 48px 0;
}
</style>

