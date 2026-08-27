<template>
  <div class="panel">
    <button @click="close"></button>
    <input v-model="query" placeholder="Search" />
    <img :src="photo.url" />
  </div>
</template>
