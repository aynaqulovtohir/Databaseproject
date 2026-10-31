// Sahifa chizilishidan oldin saqlangan ko'rinishni qo'llaydi (oq chaqnash bo'lmasin). Tashqi fayl: CSP inline skriptni taqiqlasa ham ishlaydi.
// Saqlangan qiymat faqat ruxsat etilgan ro'yxatdan olinadi. Ro'yxatlar src/lib/appearance.ts dagi bilan bir xil.
;(function () {
  var themes = ['light', 'dark', 'system', 'violet', 'green', 'wine']
  var sizes = ['md', 'lg', 'xl', 'xxl']
  function read(key, allowed) {
    try {
      var value = localStorage.getItem(key)
      return allowed.indexOf(value) >= 0 ? value : allowed[0]
    } catch (error) {
      return allowed[0]
    }
  }
  var theme = read('mb-theme', themes)
  var root = document.documentElement
  root.dataset.theme = theme
  root.dataset.textSize = read('mb-text-size', sizes)
  root.classList.toggle('dark', theme === 'dark' || (theme === 'system' && matchMedia('(prefers-color-scheme: dark)').matches))
})()
