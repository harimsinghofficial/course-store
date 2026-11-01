const loading = {};

// Load an external script once; failed loads can be retried.
export function loadScript(src) {
  if (!loading[src]) {
    loading[src] = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.async = true;
      s.onload = resolve;
      s.onerror = () => {
        delete loading[src];
        reject(new Error('script failed'));
      };
      document.head.appendChild(s);
    });
  }
  return loading[src];
}
