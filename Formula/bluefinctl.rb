class Bluefinctl < Formula
  include Language::Python::Virtualenv

  desc "TUI control panel for Bluefin OS — packages, updates, containers, devmode"
  homepage "https://github.com/projectbluefin/bluefinctl"
  url "https://github.com/projectbluefin/bluefinctl/releases/download/v0.3.0/bluefinctl-0.3.0.tar.gz"
  sha256 "b9e9cb52c9fc7a1ddb911496ee4ada5a102d10a9b4bc38948d2972cecc541fb5"
  version "0.2.1"
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
