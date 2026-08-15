(() => {
  const id = new URLSearchParams(location.search).get("id") || "";
  if (/^[A-Z0-9]{16,32}$/.test(id)) {
    location.replace("p/" + id + ".html");
    return;
  }
  location.replace("store.html");
})();
