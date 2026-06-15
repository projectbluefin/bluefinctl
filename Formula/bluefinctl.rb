class Bluefinctl < Formula
  include Language::Python::Virtualenv

  desc "TUI control panel for Bluefin OS — packages, updates, containers, devmode"
  homepage "https://github.com/projectbluefin/bluefinctl"
  url "https://github.com/projectbluefin/bluefinctl/releases/download/v0.1.0/bluefinctl-0.1.0.tar.gz"
  sha256 "0000000000000000000000000000000000000000000000000000000000000000"
  version "0.1.0"
  license "MIT"

  depends_on "python@3.13"

  resource "textual" do
    url "https://files.pythonhosted.org/packages/textual-1.0.0.tar.gz"
    sha256 "placeholder"
  end

  resource "typer" do
    url "https://files.pythonhosted.org/packages/typer-0.12.0.tar.gz"
    sha256 "placeholder"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/rich-13.0.0.tar.gz"
    sha256 "placeholder"
  end

  def install
    virtualenv_install_with_resources
  end

  test do
    assert_match "bluefinctl", shell_output("#{bin}/bctl --help")
  end
end
