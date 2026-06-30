class Bluefinctl < Formula
  include Language::Python::Virtualenv

  desc "TUI control panel for Bluefin OS — packages, updates, containers, devmode"
  homepage "https://github.com/projectbluefin/bluefinctl"
  url "https://github.com/projectbluefin/bluefinctl/releases/download/v0.4.1/bluefinctl-0.4.1.tar.gz"
  sha256 "45784012d0330e7ad3ee26efddb81b7689dcf6f1cf2e8f64200fcd5bf389ad1d"
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
