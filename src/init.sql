CREATE DATABASE IF NOT EXISTS prodprice;
CREATE DATABASE `prodprice` /*!40100 DEFAULT CHARACTER SET latin1 */;
CREATE TABLE `pp` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `product_id` bigint(20) DEFAULT NULL,
  `name` varchar(1000) CHARACTER SET utf8 DEFAULT NULL,
  `skuNames` varchar(1000) CHARACTER SET utf8 DEFAULT NULL,
  `skuIds` varchar(255) DEFAULT NULL,
  `linkUrl` varchar(255) DEFAULT NULL,
  `monthPayments` varchar(45) DEFAULT NULL,
  `months` varchar(45) DEFAULT NULL,
  `price` varchar(45) DEFAULT NULL,
  `seller` varchar(45) CHARACTER SET utf8 DEFAULT NULL,
  `create_date` datetime DEFAULT NULL,
  `update_date` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=23462 DEFAULT CHARSET=latin1;

CREATE TABLE `price` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `search_id` int(11) DEFAULT NULL,
  `product_id` bigint(20) DEFAULT NULL,
  `description` varchar(1024) CHARACTER SET utf8 DEFAULT NULL,
  `src` varchar(45) DEFAULT NULL,
  `price` int(11) DEFAULT NULL,
  `seller` varchar(45) CHARACTER SET utf8 DEFAULT NULL,
  `url` varchar(1024) DEFAULT NULL,
  `create_date` datetime DEFAULT NULL,
  `update_date` datetime DEFAULT NULL,
  `is_input` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=488 DEFAULT CHARSET=latin1;


CREATE TABLE `price` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `search_id` int(11) DEFAULT NULL,
  `product_id` bigint(20) DEFAULT NULL,
  `description` varchar(1024) CHARACTER SET utf8 DEFAULT NULL,
  `src` varchar(45) DEFAULT NULL,
  `price` int(11) DEFAULT NULL,
  `seller` varchar(45) CHARACTER SET utf8 DEFAULT NULL,
  `url` varchar(1024) DEFAULT NULL,
  `create_date` datetime DEFAULT NULL,
  `update_date` datetime DEFAULT NULL,
  `is_input` tinyint(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `id_UNIQUE` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=488 DEFAULT CHARSET=latin1;

