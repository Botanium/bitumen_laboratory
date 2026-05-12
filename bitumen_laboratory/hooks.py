app_name = "bitumen_laboratory"
app_title = "Bitumen Laboratory"
app_publisher = "Botanium"
app_description = "Laboratory module for Bitumen factory truck tests"
app_email = "botan.b.abdullah@gmail.com"
app_license = "mit"

required_apps = ["erpnext"]

before_install = "bitumen_laboratory.install.before_install"
after_install = "bitumen_laboratory.install.after_install"
before_tests = "bitumen_laboratory.install.before_tests"
