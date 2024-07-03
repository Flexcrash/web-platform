<a class="same-logo" href="https://flexcrash-project.eu/"><img data-srcset="https://flexcrash-project.eu/wp-content/uploads/2022/11/flexcrash-logo_250.png 250w, https://flexcrash-project.eu/wp-content/uploads/2022/11/FLEXCRASH_440px.png 440w" width="250" height="50" alt="flexcrash-project" data-src="https://flexcrash-project.eu/wp-content/uploads/2022/11/flexcrash-logo_250.png" data-sizes="250px" class="preload-me ls-is-cached lazyloaded" src="https://flexcrash-project.eu/wp-content/uploads/2022/11/flexcrash-logo_250.png" sizes="250px" srcset="https://flexcrash-project.eu/wp-content/uploads/2022/11/flexcrash-logo_250.png 250w, https://flexcrash-project.eu/wp-content/uploads/2022/11/FLEXCRASH_440px.png 440w"></a>


# Flexcrash Platform
This repository contains the code of the Flexcrash platform for studying live interactions between human drivers and automated vehicles (AV).
The **current version of the platform is 2.0** (See the official Deliverable D1.2 for more details about the design and operation of the platform).


## About Flexcrash
The Flexcrash project is focused on the development of a flexible and hybrid manufacturing technology to produce tailored adaptive crash-tolerant structures made of green aluminum alloys.   

The project selects vehicle parts and applies surface patterns onto performed parts with the objective to reduce weight, increase safety and optimize crash performance of current and future vehicles.  

Flexcrash solutions are to provide a general improvement of car safety with a reduction of risks and fatalities in crashes.  

Discover the project at [https://flexcrash-project.eu/about-flexcrash/](https://flexcrash-project.eu/about-flexcrash/)

### Disclaimer 
<img width="100px" data-src="https://flexcrash-project.eu/wp-content/uploads/2022/11/Flag_of_Europe.svg_.png" class=" ls-is-cached lazyloaded" src="https://flexcrash-project.eu/wp-content/uploads/2022/11/Flag_of_Europe.svg_.png">

The Flexcrash project has received funding from the Horizon Europe programme under grant agreement No. 101069674. This work reflects only the author's view. Neither the European Commission nor the CINEA is responsible for any use that may be made of the information it contains.

### Contributors:

- Dr. Alessio Gambi, PI/Lead Developer (alessiogambi, alessio.gambi@ait.ac.at)
- Benedikt Steininger (Stoneymon)
- Mykhailo Poienko (michaelpoi)
- Shreya Mattews (shreyavmatt)
- David Bobek (davidbobek)

### Get in touch!
For any question, contact us via e-mail at [info@flexcrash-project.eu](info@flexcrash-project.eu).

## Structure of the repository

```
.
├── LICENSE
├── README.md
├── deploy
├── documentation
├── entrypoint.sh
├── requirements.txt
├── src
└── videos
```

The `root` folder contains the LICENSE, `entrypoint.sh`, `requirements.txt`, and this README file.

The `src` folder contains the source code of the platform.

The `deploy` folder contains the necessary scripts to deploy the application inside `docker` using `docker compose`.

The `documentation` folder contains instruction to setup and run the platform.

The `videos` folder contains links to demonstration videos.