class Bluefinctl < Formula
  include Language::Python::Virtualenv

  desc "TUI control panel for Bluefin OS — packages, updates, containers, devmode"
  homepage "https://github.com/projectbluefin/bluefinctl"
  url "https://github.com/projectbluefin/bluefinctl/releases/download/v0.2.0/bluefinctl-0.2.0.tar.gz"
  sha256 "f43279a117502fadd58ac1953d92a9a1e4592b10a1cbda0d446784faafbe7dcb"
  version "0.2.0"
  license "MIT"

  depends_on "python@3.13"

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "bluefinctl", shell_output("#{bin}/bluefinctl --help")
    assert_match "bluefinctl", shell_output("#{bin}/bctl --help")
  end
end
