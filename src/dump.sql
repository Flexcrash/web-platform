/*!999999\- enable the sandbox mode */ 
-- MariaDB dump 10.19  Distrib 10.11.8-MariaDB, for debian-linux-gnu (x86_64)
--
-- Host: localhost    Database: Flexcrash
-- ------------------------------------------------------
-- Server version	10.11.8-MariaDB-ubu2204

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `Driver`
--

-- DROP TABLE IF EXISTS `Driver`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS `Driver` (
  `driver_id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `scenario_id` int(11) NOT NULL,
  `goal_region` varchar(250) DEFAULT NULL,
  `initial_position` varchar(250) DEFAULT NULL,
  `initial_speed` float DEFAULT NULL,
  PRIMARY KEY (`driver_id`),
  KEY `user_id` (`user_id`),
  KEY `scenario_id` (`scenario_id`),
  CONSTRAINT `Driver_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `User` (`user_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `Driver_ibfk_2` FOREIGN KEY (`scenario_id`) REFERENCES `Mixed_Traffic_Scenario` (`scenario_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `Driver`
--

LOCK TABLES `Driver` WRITE;
/*!40000 ALTER TABLE `Driver` DISABLE KEYS */;
/*!40000 ALTER TABLE `Driver` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `Mixed_Traffic_Scenario`
--

-- DROP TABLE IF EXISTS `Mixed_Traffic_Scenario`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS  `Mixed_Traffic_Scenario` (
  `scenario_id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(250) NOT NULL,
  `description` varchar(250) DEFAULT NULL,
  `created_by` int(11) NOT NULL,
  `max_players` int(11) NOT NULL,
  `n_users` int(11) NOT NULL,
  `n_avs` int(11) NOT NULL,
  `status` enum('PENDING','WAITING','ACTIVE','DONE') NOT NULL,
  `template_id` int(11) NOT NULL,
  `duration` int(11) NOT NULL,
  PRIMARY KEY (`scenario_id`),
  KEY `created_by` (`created_by`),
  KEY `template_id` (`template_id`),
  CONSTRAINT `Mixed_Traffic_Scenario_ibfk_1` FOREIGN KEY (`created_by`) REFERENCES `User` (`user_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `Mixed_Traffic_Scenario_ibfk_2` FOREIGN KEY (`template_id`) REFERENCES `Mixed_Traffic_Scenario_Template` (`template_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `Mixed_Traffic_Scenario`
--

LOCK TABLES `Mixed_Traffic_Scenario` WRITE;
/*!40000 ALTER TABLE `Mixed_Traffic_Scenario` DISABLE KEYS */;
/*!40000 ALTER TABLE `Mixed_Traffic_Scenario` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `Mixed_Traffic_Scenario_Template`
--

-- DROP TABLE IF EXISTS `Mixed_Traffic_Scenario_Template`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS  `Mixed_Traffic_Scenario_Template` (
  `template_id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(250) NOT NULL,
  `description` varchar(250) DEFAULT NULL,
  `xml` text NOT NULL,
  `is_active` tinyint(1) DEFAULT NULL,
  PRIMARY KEY (`template_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `Mixed_Traffic_Scenario_Template`
--

LOCK TABLES `Mixed_Traffic_Scenario_Template` WRITE;
/*!40000 ALTER TABLE `Mixed_Traffic_Scenario_Template` DISABLE KEYS */;
/*!40000 ALTER TABLE `Mixed_Traffic_Scenario_Template` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `User`
--

-- DROP TABLE IF EXISTS `User`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS  `User` (
  `user_id` int(11) NOT NULL AUTO_INCREMENT,
  `is_admin` tinyint(1) DEFAULT NULL,
  `username` varchar(250) NOT NULL,
  `email` varchar(250) NOT NULL,
  `password` varchar(250) NOT NULL,
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `User`
--

LOCK TABLES `User` WRITE;
/*!40000 ALTER TABLE `User` DISABLE KEYS */;
/*!40000 ALTER TABLE `User` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `UserToken`
--

-- DROP TABLE IF EXISTS `UserToken`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS  `UserToken` (
  `user_id` int(11) NOT NULL,
  `token` varchar(255) NOT NULL,
  `expiration` datetime NOT NULL,
  `is_primary` tinyint(1) NOT NULL,
  PRIMARY KEY (`token`),
  UNIQUE KEY `token` (`token`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `UserToken_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `User` (`user_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `UserToken`
--

LOCK TABLES `UserToken` WRITE;
/*!40000 ALTER TABLE `UserToken` DISABLE KEYS */;
/*!40000 ALTER TABLE `UserToken` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `Vehicle_State`
--

-- DROP TABLE IF EXISTS `Vehicle_State`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!40101 SET character_set_client = utf8 */;
CREATE TABLE IF NOT EXISTS  `Vehicle_State` (
  `vehicle_state_id` int(11) NOT NULL AUTO_INCREMENT,
  `status` enum('PENDING','WAITING','ACTIVE','CRASHED','GOAL_REACHED') DEFAULT NULL,
  `timestamp` int(11) NOT NULL,
  `driver_id` int(11) NOT NULL,
  `user_id` int(11) NOT NULL,
  `scenario_id` int(11) NOT NULL,
  `position_x` float DEFAULT NULL,
  `position_y` float DEFAULT NULL,
  `rotation` float DEFAULT NULL,
  `speed_ms` float DEFAULT NULL,
  `acceleration_m2s` float DEFAULT NULL,
  PRIMARY KEY (`vehicle_state_id`),
  KEY `driver_id` (`driver_id`),
  KEY `user_id` (`user_id`),
  KEY `scenario_id` (`scenario_id`),
  CONSTRAINT `Vehicle_State_ibfk_1` FOREIGN KEY (`driver_id`) REFERENCES `Driver` (`driver_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `Vehicle_State_ibfk_2` FOREIGN KEY (`user_id`) REFERENCES `User` (`user_id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `Vehicle_State_ibfk_3` FOREIGN KEY (`scenario_id`) REFERENCES `Mixed_Traffic_Scenario` (`scenario_id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `Vehicle_State`
--

LOCK TABLES `Vehicle_State` WRITE;
/*!40000 ALTER TABLE `Vehicle_State` DISABLE KEYS */;
/*!40000 ALTER TABLE `Vehicle_State` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2024-07-03  7:37:19
