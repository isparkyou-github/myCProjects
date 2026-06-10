// 最小化 Service Worker：满足 PWA 可安装条件，不做离线缓存
// （发布与数据接口都需要实时后端，离线缓存意义不大）
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("fetch", () => {});
