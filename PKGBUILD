# Maintainer: rendogust <rendogust@gmail.com>
# Contributor: romelium

pkgname=mpatch-bin
pkgver=1.5.0
pkgrel=1
pkgdesc='Applies diffs based on context, not line numbers. Useful for AI-generated code.'
arch=('x86_64' 'aarch64' 'armv7h')
url='https://github.com/Romelium/mpatch'
license=('MIT')
provides=('mpatch')
conflicts=('mpatch')

# Upstream target triples per architecture
# Arch uses glibc, so we use the gnu triples (not musl)
_triple_x86_64="x86_64-unknown-linux-gnu"
_triple_aarch64="aarch64-unknown-linux-gnu"
_triple_armv7h="armv7-unknown-linux-gnueabihf"

source_x86_64=("mpatch-${pkgver}-${_triple_x86_64}.tar.gz::https://github.com/Romelium/mpatch/releases/download/v${pkgver}/mpatch-${_triple_x86_64}-v${pkgver}.tar.gz")
source_aarch64=("mpatch-${pkgver}-${_triple_aarch64}.tar.gz::https://github.com/Romelium/mpatch/releases/download/v${pkgver}/mpatch-${_triple_aarch64}-v${pkgver}.tar.gz")
source_armv7h=("mpatch-${pkgver}-${_triple_armv7h}.tar.gz::https://github.com/Romelium/mpatch/releases/download/v${pkgver}/mpatch-${_triple_armv7h}-v${pkgver}.tar.gz")

sha256sums_x86_64=('cb8c272dbfc7151c1da1c284962076a5d2869186588c723748639b4da7a8953d')
sha256sums_aarch64=('6b8a725042dd24fbcddf0d1ed79644578bef7eca7064622b3bc25ff52583e527')
sha256sums_armv7h=('1bd714a9d5f93020efbdf66ff0705163e5d616b243a212bc5b12d18d72210321')

package() {
  # Determine the triple from the source URL that was actually downloaded
  local _triple
  case "${CARCH}" in
    x86_64)  _triple="${_triple_x86_64}" ;;
    aarch64) _triple="${_triple_aarch64}" ;;
    armv7h)  _triple="${_triple_armv7h}" ;;
  esac

  cd "${srcdir}/mpatch-${_triple}-v${pkgver}"

  install -Dm755 mpatch "${pkgdir}/usr/bin/mpatch"
  install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
  install -Dm644 README.md "${pkgdir}/usr/share/doc/${pkgname}/README.md"
}
