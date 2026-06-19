class Bluefinctl < Formula
  include Language::Python::Virtualenv

  desc "TUI control panel for Bluefin OS — packages, updates, containers, devmode"
  homepage "https://github.com/projectbluefin/bluefinctl"
  url "https://github.com/projectbluefin/bluefinctl/releases/download/v0.2.1/bluefinctl-0.2.1.tar.gz"
  sha256 "dfedcb7104abf307c8f6d8544e2e15a67ecd598459fe10dd609423af7abedd5a"
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
