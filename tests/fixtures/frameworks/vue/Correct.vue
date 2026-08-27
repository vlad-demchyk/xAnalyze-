<template>
  <div class="panel">
    <button :aria-label="closeLabel" @click="close">×</button>
    <label for="q">{{ searchLabel }}</label>
    <input id="q" v-model="query" />
    <img :src="photo.url" :alt="photo.caption" />
  </div>
</template>
