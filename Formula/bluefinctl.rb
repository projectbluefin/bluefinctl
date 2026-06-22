class Bluefinctl < Formula
  include Language::Python::Virtualenv

  desc "TUI control panel for Bluefin OS — packages, updates, containers, devmode"
  homepage "https://github.com/projectbluefin/bluefinctl"
  url "https://github.com/projectbluefin/bluefinctl/releases/download/v0.4.0/bluefinctl-0.4.0.tar.gz"
  sha256 "f204e99be8636fd60d8e6ceb77b8e8063c2de73b1d91a892fa71d2afedfab981"
  version "0.4.0"
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
