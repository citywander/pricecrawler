CREATE DATABASE `prodprice` /*!40100 DEFAULT CHARACTER SET latin1 */;
CREATE TABLE `pp` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(1000) CHARACTER SET utf8 DEFAULT NULL,
  `skuNames` varchar(1000) CHARACTER SET utf8 DEFAULT NULL,
  `skuIds` varchar(255) DEFAULT NULL,
  `linkUrl` varchar(255) DEFAULT NULL,
  `monthPayments` varchar(45) DEFAULT NULL,
  `months` varchar(45) DEFAULT NULL,
  `price` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2822 DEFAULT CHARSET=latin1;
CREATE TABLE `price` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `product_id` int(11) DEFAULT NULL,
  `price` int(11) DEFAULT NULL,
  `src` varchar(45) DEFAULT NULL,
  `url` varchar(45) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=latin1;
CREATE TABLE `product` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `keywords` varchar(1000) DEFAULT NULL,
  `describe` varchar(1000) DEFAULT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=55 DEFAULT CHARSET=utf8;
