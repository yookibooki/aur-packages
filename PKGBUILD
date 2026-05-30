# Maintainer: mpatch AUR maintainer <your-email@example.com>
# Contributor: romelium

pkgname=mpatch-bin
pkgver=1.5.0
pkgrel=1
pkgdesc='Applies diffs based on context, not line numbers. Useful for AI-generated code.'
arch=('x86_64' 'aarch64')
url='https://github.com/Romelium/mpatch'
license=('MIT')
provides=('mpatch')
conflicts=('mpatch')
source_x86_64=("mpatch-${pkgver}-x86_64.tar.gz::https://github.com/Romelium/mpatch/releases/download/v${pkgver}/mpatch-x86_64-unknown-linux-gnu-v${pkgver}.tar.gz")
source_aarch64=("mpatch-${pkgver}-aarch64.tar.gz::https://github.com/Romelium/mpatch/releases/download/v${pkgver}/mpatch-aarch64-unknown-linux-gnu-v${pkgver}.tar.gz")
sha256sums_x86_64=('cb8c272dbfc7151c1da1c284962076a5d2869186588c723748639b4da7a8953d')
sha256sums_aarch64=('6b8a725042dd24fbcddf0d1ed79644578bef7eca7064622b3bc25ff52583e527')

package() {
  cd "${srcdir}/mpatch-${CARCH}-unknown-linux-gnu-v${pkgver}"

  install -Dm755 mpatch "${pkgdir}/usr/bin/mpatch"
  install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
  install -Dm644 README.md "${pkgdir}/usr/share/doc/${pkgname}/README.md"
}
