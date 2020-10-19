# essay

## Requirment
 - docker
 - docker-compose

 ## Deploy and run

```
https://github.com/csbbo/essay.git
cd essay
sudo bash package.sh
sudo bash deploy.sh
```

running in port 80

> Because the dependent library **wkhtmltopdf** requires an interactive installation and cannot be installed at packaging time, you need to go into the **essay_server** container and use the command `apt install wkhtmltopdf` to install it.