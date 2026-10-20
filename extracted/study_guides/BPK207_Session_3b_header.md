# Lecture Reference Header: BPK 207 (Session/Chapter 3b)

## 1. Course Pedagogical Profile & Rules
# Course Profile: BPK 207 — Sensorimotor Control & Learning

## 1. Course Metadata & Naming Conventions
- **Course Code:** `BPK207` (`BPK 207`)
- **Course Title:** Sensorimotor Control & Learning
- **Target Deck File Pattern:** `BPK 207 - Sensorimotor Control & Learning Anki.apkg` (Drive ID: `1pONTJ5FBDRKogzGzJD8r41df1AWJR14V`)
- **Deck Name inside Anki:** `BPK 207 - Sensorimotor Control & Learning`
- **Tag Format:** `#BPK207::Chapter::<Chapter_Number>` (e.g., `#BPK207::Chapter::1`, `#BPK207::Chapter::2`, `#BPK207::Chapter::3a`, `#BPK207::Chapter::3b`)
- **Shared Google Drive Folder ID:** `1JD0rlrkJIFJ6n4hv5Mxc9zLSP-UEZJja`

---

## 2. Modality & Card Design Preferences
- **Image / Diagram Usage:**
  - `[x] Include Slide Figures in Extra Field` (Run `anki_cli.py inspect --extract-images` and embed key illustrative diagrams `<img src="filename.jpeg">` alongside concise high-yield notes in `extra`).
- **Primary Focus Areas:**
  - Sensorimotor terminology, definitions, and functional roles (e.g., sensory feedback, proprioception, somatotopy, range fractionation, labelled line coding).
  - Neurophysiological mechanisms relevant to movement control (e.g., frequency coding vs. population coding, slowly vs. rapidly adapting receptors, muscle spindles [intrafusal bag1/bag2/chain, Ia vs. II afferents, dynamic/static gamma motoneurons, alpha-gamma co-activation], Golgi tendon organs [Ib afferents, in-series tension sensing], monosynaptic stretch reflex vs. disynaptic reciprocal inhibition).
  - Experimental paradigms & clinical conditions (e.g., surgical vs. temporary deafferentation, sensory neuropathy, muscle/tendon vibration illusions & Pinocchio effect, two-point discrimination).
  - Ascending pathways & cortical representations (DCML tract vs. spinocerebellar tracts, S1 / Brodmann areas 3, 1, 2, sensory homunculus).
- **Respect Slide Annotations & Exclusions:**
  - Always check the extracted slide text and images for Mara's handwritten notes, highlights, stars (`*`), and exclusions (e.g., if a slide section is marked *"Don't need to know"* or explicitly stated as non-testable background in the text, skip or keep only the testable distinction).
  - Group clozes (`c1`, `c2`, `c3`) cleanly so each card tests an atomic concept, list with explicit item counts, or cause-and-effect relationship.

---

## 3. Coordinated Functional Cloze Grouping (Tiered Category & Detail Rule)
When testing contrasting pairs, anatomical structures, or categorized lists, NEVER assign sequential arbitrary cloze numbers (e.g. `{{c1::A}} ({{c2::X}}) and {{c3::B}} ({{c4::Y}})`).
Group parallel elements into coordinated tiers:
- **`c1` (The Structural / Entity Tier):** Cloze all anatomical structures, end organs, or category labels together.
- **`c2` (The Functional / Coordinate / Detail Tier):** Cloze all corresponding physiological roles, planes of motion, axes, or mechanisms together.

### Benchmark Examples to Follow:
- **Vestibular End Organs:**
  `"The vestibular system detects head acceleration using two sets of end organs: the {{c1::otoliths}} (which sense {{c2::linear}} acceleration) and the {{c1::semicircular canals}} (which sense {{c2::angular}} acceleration)."`
- **Otolith Organs & Spatial Planes:**
  `"Within the otolith organs, the {{c1::saccule}} senses acceleration in {{c2::the vertical plane}}, whereas the {{c1::utricle}} senses acceleration in {{c2::the horizontal plane}} as well as {{c2::head tilt}} relative to gravity."`
- **Rotational Dimensions & Axes:**
  `"The semicircular canals sense angular head acceleration across three rotational dimensions: {{c1::roll}} (around {{c2::x}}-axis), {{c1::pitch}} (around {{c2::y}}-axis), and {{c1::yaw}} (around {{c2::z}}-axis)."`
- **Muscle Spindle Fibers & Sensory Afferents:**
  `"Within the muscle spindle, {{c1::dynamic bag1}} fibres are innervated primarily by {{c2::Group Ia}} afferents, whereas {{c1::static bag2 and chain}} fibres are innervated primarily by {{c2::Group II}} afferents."`
- **Motor State & Reflex Regulation:**
  `"Depending on motor state, Golgi tendon organ (Ib) feedback acts to {{c2::inhibit muscle force}} during {{c1::stationary overload/fatigue}}, but {{c2::excite extensor activity}} during {{c1::locomotion (walking)}}."`

---

## 4. The "Support-Only" Extra Field Rule & Extra Extraction Principle
- **Support-Only Extra:** The `extra` field exists strictly to support the tested clozes (via diagram grounding `<img src="...">`, cross-referencing other cards, or a 1-sentence physiological rationale). It must NEVER introduce new, untested concepts, anatomical structures, or cascades.
- **The Testability Axiom:** If a piece of information is testable on an exam, it MUST have its own active-recall Cloze card.
- **Extra Extraction Check:** Before finalizing `extra`, ask: *"Does this contain a key term, mechanism, or step that could be asked on an exam?"* If YES, extract it out into a dedicated card and keep `extra` strictly supportive!

---

## 5. Bidirectional Definition Testing Rule (Term ↔ Meaning)
When a note tests a definition, scientific concept, or physiological process, test it in BOTH directions:
- **`c1` (Term Recall):** `[Definition] → [Term]`
- **`c2` (Definition / Functional Role Recall):** `[Term] → [What it actually means/does]`
- **`c3` (Effector / Driver Tier, if applicable):** Anatomical structure, effector muscle, or mechanism driving the process.

### Benchmark Example:
`"{{c2::The dynamic process of altering the shape and curvature of the crystalline lens to focus objects at varying distances onto the retina}} is called {{c1::accommodation}}, which is driven by the contraction and relaxation of the {{c3::ciliary muscles}}."`


## 2. Slide-by-Slide Lecture Content & Figure Inventory

### Slide 1
- **Detected Sub-Sections:** 3b.1 Section Learning Outcomes:  By the end o, 3b.2 VESTIBULAR SYSTEM:  •  Detects head acce, 3b.2.1 Vestibular system detects linear and ang
- **Extracted Slide Figures:** slide_01_fig_1.jpeg, slide_01_fig_2.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
1
SECTION 3B: SENSORY CONTRIBUTION – Part 2
3b.1 Section Learning Outcomes:  By the end of this section, you will be able to…
1. Explain how the vestibular organs signal head acceleration/orientation  2. Define the pathways transmitting visual information to the visual cortex and beyond, and  their role in movement  3. Describe how the visual system processes motion  4. Explain how sensory input is integrated to guide movement
3b.2 VESTIBULAR SYSTEM:  •  Detects head acceleration
– Helps determine head position/motion
and body orientation  •  Components (called end organs):
– Otoliths
•  Saccule   •  Utricle  – Semicircular canals
•  Superior, posterior, horizontal  •  Boxed labels in top figure are most important for  this course  •  Vestibular apparatuses on both sides of head  work together to signal head movement or  orientation
– Allows for a greater signal-to-noise ratio,
and thus increases sensitivity to motion    3b.2.1 Vestibular system detects linear and angular head acceleration:  •  Otoliths:
– Sense linear head acceleration (i.e., changing translational motion through
environment) and changes in head orientation relative to gravity  – Saccule detects acceleration in vertical plane  – Utricle detects acceleration in horizontal plane, as
well as head tilt  •  Semicircular canals:
– Sense angular head acceleration
•  Turning or tilting  •  Rotatory body movements    Head movement is a combination of rotations and linear motion  in various planes. Rotational planes include roll, yaw, and pitch  (see figure at right). Vestibular system can detect head movement in all directions/rotations.
÷:*:"

### Slide 2
- **Detected Sub-Sections:** 3b.2.2 Vestibular transduction:  How do vestibu
- **Extracted Slide Figures:** slide_02_fig_1.jpeg, slide_02_fig_2.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
2
3b.2.2 Vestibular transduction:  How do vestibular end organs convert head motion into electrical signals the nervous system can use?  Otoliths and semicircular canals (and the cochlea) rely on the deflection of hair cells.
Tiny structures called “’tip links” connect individual hairs together (see above on right) and are  connected to spring-gated ion channels. When the head is upright and not accelerating, cilia/hairs are  in a middle position and there is a small amount of activity (“resting discharge”) in vestibular afferents  that come from the otoliths and semicircular canals. This is because tip links slightly open the ion  channels and allow a small amount of K+ inside. When hair cells are bent toward the kinocilium, tip  links open the ion channels more. When hair cells are bent away from the kinocilium, tip links close  the ion channels. This leads to depolarization (and increased afferent discharge) and  hyperpolarization (and decreased afferent discharge), respectively.    How do the semicircular canals signal angular acceleration?
The canals are filled with a viscous fluid,  which is rich in K+, called endolymph.  Because of its inertia, when the head  rotates, the endolymph lags behind the  canal itself (like how coffee within a  rotated mug will lag behind the wall of  the mug). The endolymph displaces a  gelatinous structure called the cupula.  This structure has hair cells embedded  in it (which are deflected). See figure on  the left.
↳ sensing

### Slide 3
- **Extracted Slide Figures:** slide_03_fig_1.jpeg, slide_03_fig_2.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
3
In the figures below, we see how the canals signal the direction of head rotation. The endolymph  movement shown below is relative to the head. From an external (inertial) frame of reference, the  endolymph is staying still and the head+cupula+hair cells are what’s really moving.
How do the otoliths signal head acceleration?
•  Linear (translational) head motion through environment OR change in head orientation  relative to gravity (e.g., head pitch downward) causes movement of otolithic membrane
– Otolithic membrane (containing otoconia stones) lags behind head motion
•  Deflects hair cells (which project up into this membrane)  •  Imagine holding a plate with a cookie on it. The cookie represents the otolithic  membrane. If you accelerate the plate forward (or lean the plate back) the  cookie slides back. If your plate had hair cells under the cookie, they would  “feel” this backward motion. See figure below.
The example above shows utricle signaling but the mechanism is similar in the saccule.

### Slide 4
- **Detected Sub-Sections:** 3b.2.3 Functions of the vestibular system:  •  , 3b.2.4 Galvanic vestibular stimulation (GVS) is, 2.4.9 Non-invasive neurostimulation). GVS acti
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
4
For both the canals and the otoliths, the key to detecting acceleration is having an inertial substance  (endolymph or otolithic membrane) that is not rigidly attached to the rest of the body.  When the  body accelerates, inertia causes the substance to lag behind and hair cells detect this relative motion.      3b.2.3 Functions of the vestibular system:  •  Postural stabilization
– Maintenance of balance
•  Via vestibulospinal reflexes
•  Vestibular afferents project to vestibular nuclei in brainstem, which  gives rise to descending tracts that activate muscles  – Helps keep head upright (and perception of spatial orientation when head not upright)
•  Gaze stabilization (in conjunction with visual system)
– Via vestibular-ocular reflex (VOR)
•  This reflex compensates for head movement  •  When head moves, the eyes rotate in orbits to maintain gaze fixation on target  of interest
•  Perception of self-motion
– Head motion can tell central nervous system (CNS) about your motion
•  Role in spatial navigation
– Linked with self-motion as well as knowing orientation      3b.2.4 Galvanic vestibular stimulation (GVS) is used to study the vestibular contribution to  balance:  Weak direct current is applied through electrodes placed over the mastoid bones behind the ears. It is  similar to tDCS (Section 2.4.9 Non-invasive neurostimulation). GVS activates the vestibular afferents  and hair cells of the otoliths and semicircular canals causing illusory perception of head (and body) tilt  and compensatory tilt in the opposite direction (analogous to muscle vibration of the legs, Section  3a.4.5).    The figure below demonstrates the effect of GVS on standing balance, supporting the role of the  vestibular system in this task.

### Slide 5
- **Detected Sub-Sections:** 3b.3 VISUAL SYSTEM:  The visual system is a c, 3b.3.1 The eye:  •  Eye is designed to focus th
- **Extracted Slide Figures:** slide_05_fig_1.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
5
GVS causes the illusory perception of sway toward the cathode and there is resulting compensatory  sway toward the anode. (We only see the compensatory sway, of course.) Diagram on left shows  alignment of the body after stimulation. In this example, the anode (+) is on the participant’s right and  they lean to the right. Plots show sway responses for the pelvis, trunk, and head segments for GVS  delivered during the period indicated by the 4-s bar at bottom. The thick up-going traces are with  anode-right GVS, and the thin down-going traces are with anode-left GVS. (As shown on the left, each  body segment tilts on the one below it so that the greatest tilt is at the head.) Right plots show that  sway is greatly attenuated when standing with the feet apart. Shortly after stimulus onset, the body  moves toward the anodal side before reaching a steady angle. When the stimulus stops, the segments  straighten to their original positions. The figure on the far right show vestibular afferent activity  caused by GVS.
3b.3 VISUAL SYSTEM:  The visual system is a complex (and very well studied) sensory system. A large portion of the human  brain is involved in processing (or analyzing) visual information. In this course, we will only cover  aspects related to movement (or necessary to understand how vision contributes to movement).    3b.3.1 The eye:  •  Eye is designed to focus the visual image on the retina with minimal optical distortion
•  The parts you should know are indicated by boxes in the figure below  •  The fundus is what a physician sees when they look into your eye with an  ophthalmoscope  •  Light is focused by the cornea and lens onto photoreceptors in the retina

### Slide 6
- **Detected Sub-Sections:** 3b.3.2 Retina is where the magic happens:  •  R
- **Extracted Slide Figures:** slide_06_fig_1.jpeg, slide_06_fig_2.jpeg, slide_06_fig_3.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
6
•  Light rays must converge at the retina for  light to be in focus  •  Light is refracted when it passes through the  cornea (2/3 of total refraction here), then at  the lens (1/3 of total refraction here)
– Only the lens can change its shape to
alter the distance at which objects will  be in focus
•  Known as “accommodation”
•  Due to contraction/relaxation of the ciliary muscles    3b.3.2 Retina is where the magic happens:  •  Retina contains numerous cells (including 5 different types of neurons) in multiple layers
•  Details on this complexity are discussed in other courses  •  Photoreceptors (rods & cones) transduce light into electrical signals  •  Fovea is the part of the retina that allows vision of fine details  •  Fovea contains only cones; rods dominate the retina elsewhere  •  Retinal ganglion cells form the optic nerve & propagate the signal to visual areas of the brain

### Slide 7
- **Detected Sub-Sections:** 3b.3.3 Central versus peripheral vision:  •  Vi, 3b.3.4 Visual fields and visual pathways:  Use 
- **Extracted Slide Figures:** slide_07_fig_1.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
7
The retina lies in front of the pigment epithelium that lines the back of the eye. Cells in the pigment  epithelium are filled with a black pigment, melanin, which absorbs any light not captured by the  photoreceptors. This prevents light from being reflected off the back of the eye, which would degrade  the visual image. Light must travel through the layers of other retinal neurons before striking the  photoreceptors. Cell bodies of the proximal retinal neurons in the fovea are shifted to the side,  enabling the photoreceptors to receive the visual image in its least distorted form.    Recall that we need to make saccades (see Section 1.6.4), so images are projected onto the fovea,  which has the greatest number of cone photoreceptors and best resolution (i.e., best visual acuity).      3b.3.3 Central versus peripheral vision:  •  Visual field
– The region of space the eye sees  – Shifts with eye movements  •  Central vision
– Deals with identifying details  – Central ~5° of visual field  – Predominantly contains cones  •  Peripheral vision
– Deals with where things are  – Information regarding environmental context and
moving limb  – Contains mostly rods and sparse cones          3b.3.4 Visual fields and visual pathways:  Use the figures below to trace the pathway that electrical signals related to images in the visual field  take to reach the visual cortex in the back of the brain. All labelled areas are important to know. Note  especially the following: temporal and nasal hemiretina (and how the retinal ganglion cells that  originate in the latter cross at the optic chiasm); ganglion cells synapse at the lateral geniculate  nucleus (LGN) of the thalamus; and the left visual field is processed in the right hemisphere and vice  versa.

### Slide 8
- **Extracted Slide Figures:** slide_08_fig_1.jpeg, slide_08_fig_2.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
8
To test your understanding of visual fields and visual pathways, consider the following lesions  (denoted by the thick black lines) and their effects:

### Slide 9
- **Detected Sub-Sections:** 3b.3.5 Binocular retinal disparity:  Binocular , 3b.3.6 Primary visual cortex (V1):  •  Like all
- **Extracted Slide Figures:** slide_09_fig_1.jpeg, slide_09_fig_2.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
9
3b.3.5 Binocular retinal disparity:  Binocular disparity refers to the difference in image location of an object  seen by the left and right eyes, resulting from the eyes' horizontal  separation (parallax). Depth perception is facilitated by the difference in  image location of an object as viewed by the left and right eyes.    See the figure on the right (how we perceive distance of images given a  stable fixation point):
•  Note that depending on where you fixate the light rays of the  object hit a different part of the retina  •  Integrating this disparity leads to the perception of depth    Binocular retinal disparity can be used to process object motion
•  If object moves (e.g., from A to B) and the eyes remain fixed, the  image activates the retina progressively more laterally    Try this activity:  1. Hold out your left index finger at about a foot from your nose and your  right index finger halfway between your nose and other finger. (Make sure you can see your far-left  finger over your right finger – don’t block it.) Keep both eyes open and look with both eyes.  2. While looking at far (left) finger, notice the close (right) one is doubled – that’s like the pink square.  3. Keep looking at the left finger. Move the right finger out so it’s next to the left one. You’ll see it’s no  longer doubled.  4. Move your right finger farther out (keep looking at left one) - right is doubled again.    This only works if you are careful about which finger you’re focusing on. When a finger looks doubled,  its image is falling on mismatched places on the retinas.    3b.3.6 Primary visual cortex (V1):  •  Like all neocortex, about 2 mm thick and consists of 6 layers
– Neurons carrying visual input from LGN enter layer 4
•  Also known as visual striate cortex (and Brodmann area 17)
– “Striate” means striped
•  This area has a prominent layer 4 that gives rise  to a striped appearance in V1 cross sections
•  Contralateral visual field representation is preserved in V1
– Note retinotopic representation
•  Light (images) from specific areas of visual field  hits a specific part of retina; each specific part  of retina is mapped onto the visual cortex (note  #’s in figure).  So, like the somatotopically  organized somatosensory cortex (Section  3a.4.8), adjacent points in sensory space are  represented at adjacent points in the brain.

### Slide 10
- **Detected Sub-Sections:** 3b.3.7 Receptive field properties of neurons in
- **Extracted Slide Figures:** slide_10_fig_1.jpeg, slide_10_fig_2.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
10
•  Has cells with many different visual receptive field types, including:
– Layer 4c, simple, and complex cells (see below)  – Recall the concept of tactile receptive fields (Section 3a.3.4.4)    3b.3.7 Receptive field properties of neurons in the visual pathway:  •  Retinal ganglion and lateral geniculate nucleus (LGN) neurons have receptive fields such that  each neuron responds to a tiny spot of light (think of this as a tiny region of the visual field)
– Layer 4c neurons in V1 (onto which LGN neurons
synapse) are similar
•  Simple cells in V1 have elongated receptive fields
– Sense lines/edges of a particular orientation  – Respond to bars of light and borders between light and
dark (thus they can detect an edge of an object)
•  Complex cells in V1 have larger receptive fields
– Sense lines/edges of a particular orientation anywhere
within the receptive field  – Many also are sensitive to moving lines/edges
•  Respond to moving bars of light
•  Note hierarchical organization (see figure on right and below)
– Receptive fields get bigger as you move from LGN to visual cortex (from layer 4c to
simple to complex cells)  – At each step in the hierarchy, when receptive fields get more complex, a receptive field
is the sum of multiple, smaller receptive fields from “upstream” neurons (those that  synapse onto the “downstream” neuron).

### Slide 11
- **Detected Sub-Sections:** 3b.3.8 Neuronal tuning curves:  In this example, 3b.3.9 Many areas of the brain process visual i
- **Extracted Slide Figures:** slide_11_fig_1.png
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
11
In figure above, orange circles at left are receptive fields of layer 4c cells (or LGN or retinal ganglion  cells). Blue ovals are receptive fields of simple cells (each the sum of several layer 4c receptive fields),  and the purple box is the complex cell receptive field (sum of several simple cell receptive fields). This  receptive field construction arises from the circuitry shown on the right.    This hierarchical organization is a fundamental principle of how information is integrated (and  expanded) from one level to another within the nervous system. In other words, this idea applies to  many brain areas and many different senses.    As noted above, neurons in V1 respond to particular orientations of light. We can see this with a  neuronal tuning curve, which is described next.      3b.3.8 Neuronal tuning curves:  In this example, to create a tuning curve for a single visual cortex neuron, you project a bar of light in  a particular orientation on a screen and record the activity of the neuron. Repeat this for different  stimulus orientations, then plot the relationship.
3b.3.9 Many areas of the brain process visual input: striate and extrastriate visual cortex  Note: extrastriate refers to all cortical visual areas outside of V1 (a.k.a. Brodmann area 17 or striate  cortex)

### Slide 12
- **Detected Sub-Sections:** 3b.3.10 Cortical regions important for processin
- **Extracted Slide Figures:** slide_12_fig_1.jpeg, slide_12_fig_2.jpeg, slide_12_fig_3.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
12
From: Felleman & Van Essen 1991      Note: the figure above on the right shows just how complex the circuitry is for processing visual  information in the primate cortex. You do NOT need to know that level of detail for this course.  Information flows upward from retinal ganglion cells (RGC) to LGN to V1 and so on. Many connections  are bidirectional (that is, flows in both directions using different neurons).      3b.3.10 Cortical regions important for processing visual motion (optic flow):  •  Middle temporal (MT) region [also called area V5]
– Neurons have large receptive fields  – Neurons have preference for a certain direction of motion  – Neuronal activity is sensitive to (i.e., discharge is based on) speed of motion  – Projects to MST region  •  Medial superior temporal (MST) region
– Divided into two sub-regions that process object-motion or self-motion  – Neurons have large receptive fields (larger than MT)    The figure below shows the approximate locations of MT and MST and how visual motion is used for  different functions.

### Slide 13
- **Detected Sub-Sections:** 3b.3.11 Optic flow provides information relevant
- **Extracted Slide Figures:** slide_13_fig_1.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
13
3b.3.11 Optic flow provides information relevant for movement:  •  Optic flow is “the continuous change over time of the spatial pattern of light (variations in  intensity and wavelength composition) reaching a point as it moves through its surroundings”  (Tresilian 2012)
– Movement patterns of light rays from the environment over a person’s retina, allowing
a person to perceive motion, position, and timing  – Abrupt changes in pattern correspond to boundaries and features in the environment  – The figure below shows what optic flow looks like
•  Note that we don’t actually “see” the lines/dashes (they are present to simulate  it, just like when you see stars stretch in TV shows and movies to indicate the  spaceship is moving; think warp speed or lightspeed in Star Trek or Star Wars)      Components/types of optic flow:
•  Whole field motion
– Motion of an image sweeping across the eye when an eye rotates in its socket with the
head stationary (from the image moving relative to the retina)  – Like looking left to right without moving head
•  Image flow caused by the eye moving through the environment as a person moves and the  eye turning in its socket simultaneously is composed of two parts:
– Translational flow (see panel B in figure below on right)
•  Referred to as radial outflow in figure below on left)  •  Motion due to movement of eye through environment  – Rotational flow (see panel C in figure below on right)
•  Motion due to the eye turning within the environment

### Slide 14
- **Detected Sub-Sections:** 3b.3.12 Visual input allows a person to determin, 3b.3.13 Dorsal and ventral visual streams (the t
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
14
Note radial outflow panel of figure above. The lines appear to originate from the centre. This is what  your eyes see as you walk forward with gaze straight ahead.    Two factors are important for generating optic flow: (1) the speed and direction of the eye’s  movement through the surrounding; and (2) the distances from the eye to the points in the  surroundings that hit the retina. Images of closer objects flow across the eye faster when the eye  moves through space.    Optic flow provides information on:
•  Stability & balance
– Postural sway generates optic flow
•  No sway, no flow  •  In the SOT (Section 2.4.2), the sway-surround condition eliminates optic flow  •  Velocity & direction of movement
– Self-motion  – Walking generates flow as photons of light reflecting off objects and surfaces enter
your eye  •  Movement of objects in the environment
– Moving objects reflect light into your eye  •  Time-to-contact (see below)      3b.3.12 Visual input allows a person to determine time-to-contact (TTC) with objects:  TTC serves predictive function:
•  Can use for movement initiation  •  Critical for avoidance and interceptive behaviours (even insects have looming sensitive  neurons)    There are several ways to calculate TTC, including from:
– Optic flow (Lee 1976)
•  Calculate ratio of the object’s image size to the rate of its radial expansion on  the retina; a variable called tau  – Binocular retinal disparity  – Oculomotor vergence feedback
•  Feedback from muscle spindles in eyes as the eyes rotate inward or outward to  track an object      3b.3.13 Dorsal and ventral visual streams (the two visual systems idea):  There is some evidence that there are at least two major different visual pathways (or streams) in the  visual system that contribute to different functions.
•  Vision-for-perception system
– Ventral visual stream – primary visual cortex to temporal lobe  – Responsible for fine analysis of the visual scene (form, colour) and object recognition

### Slide 15
- **Extracted Slide Figures:** slide_15_fig_1.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
15
– Uses object-centred frame of reference
•  E.g., The laptop is X distance to the coffee mug  – A.k.a., the ‘what’ stream (i.e., “what is that”)
•  Vision-for-action system
– Dorsal visual stream – primary visual cortex to posterior parietal cortex and beyond  – For guiding movement and spatial characteristics of the environment  – Uses various egocentric frames of reference (e.g., retinotopic, head-centred, limb-
centred, gaze-centred); i.e., body-based frame of reference
•  E.g., The laptop is X distance to your hand  – A.k.a., the ‘how’ or ‘where’ stream (i.e., “where is it” and “how do I interact with it”)
•  There is an interaction and overlap between the two visual streams when performing goal- directed movement      What is the evidence for two different visual streams? Researchers performed a series of experiments  involving individuals with brain lesions (i.e., damage) specific to the brain area(s) of one but not the  other visual stream. One set of experiments is described below.
•  Tasks:
– Same-different discrimination task
•  Two shapes presented together, and  participant asked to determine visually if  they are the same or different  – Object manipulation task
•  Grasp shape appropriately  •  Grasp requires placing thumb and index  finger at stable points
•  S.H. is a healthy control
•  Damage to dorsal stream (i.e., R.V.) results in an  improper grip of object even though able to visually  discriminate
•  Damage to ventral stream (i.e., D.F.) results in an inability  to discriminate between shapes but proper grasping    This experimental design allows for a result called a “double dissociation,” which is compelling  evidence for the two separate functions: (1) Vision for “how do I interact with that?” (effective  grasping) and (2) vision for “what is that” (discrimination/identification). It is possible to have (1) but  not (2) OR (2) but not (1).     The following figure shows the anatomical location of the dorsal and ventral visual streams:

### Slide 16
- **Detected Sub-Sections:** 3b.3.14 Vision and specific motor behaviours:  V
- **Extracted Slide Figures:** slide_16_fig_1.jpeg, slide_16_fig_2.jpeg
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
16
The figure also shows that colour, form, and motion are processed in separate pathways in the cortex.  Other details (including midget and parasol ganglion cells, layers of V1, the stripes and blobs) unique  to this figure are not important for this course.      3b.3.14 Vision and specific motor behaviours:  Visual feedback is important for many different motor behaviours. It provides information on the  layout of the environment, characteristics of objects and surfaces, and self- and object-motion. Here  we briefly describe its contribution to standing balance, locomotion, and reaching.    Vision contributes to standing balance:
•  Importance of vision for balance shown with ‘moving room’ experiments (Lee & Aronson 1974):
– Walls and ceiling, but not floor, moved forward
or backward  – With visual and somatosensory input in conflict,
the participants gave primacy to vision and  initiated unnecessary postural adjustments  – Infants fall over; adults sway more  – The SOT test also manipulates visual
information, but in a different way (Section  2.4.2)

### Slide 17
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
17
Vision contributes to locomotion:  Vision plays an essential role in guiding locomotion:
•  Implementing avoidance strategies (e.g., related to curbs, pedestrians)  •  Accommodating different terrain  •  Navigation and determining the direction of walking (heading direction)  •  Planning and controlling precise foot placement
– People tend to fixate where they eventually step; look-ahead distance depends on the
complexity of the terrain (distance decreases with more complex terrain)  •  Vision is used to monitor lower limb trajectory when stepping over obstacles  •  Vision is used both to plan upcoming movement and as sensory feedback to correct the  movement on-line (i.e., as it unfolds)      Vision contributes to reaching:
•  Vision provides extrinsic, world-based coordinate information
– Used to plan spatial features of movements toward visual targets  •  Vision also provides information regarding initial limb (hand/arm) configuration  •  Absence of vision of hand/arm during reaching results in changes in movement kinematics  (e.g., longer movement time) and decreased accuracy  •  Research suggests that we use visual feedback continuously during the movement or after the  initial (very early) phase of the movement

### Slide 18
BPK 207 – Sensory Contribution (part 2)  Copyrighted material  Simon Fraser University
18
REFERENCES (AND SOURCES)  •  Boron WF, Boulpaep EL. Medical physiology, 2nd edition. Saunders, Elsevier, 2009.  •  Felleman & Van Essen. Distributed Hierarchical Processing in the Primate Cerebral Cortex. Cerebral Cortex 1: 1-47,  1991.  •  Fitzpatrick RC, Day BL. Probing the human vestibular system with galvanic stimulation. J Appl Physiol 96: 2301-2316,  2004.  •  Gilaie-Dotan S. Visual motion serves but is not under the purview of the dorsal pathway. Neuropsychologia 89: 378- 392, 2016.  •  Ivanenko YP et al. J Neurophysiol 84: 1737-1747, 2000.  •  Johansson RS, Flanagan JR. Coding and use of tactile signals from the fingertips in object manipulation tasks. Nat Rev  Neurosci 10: 345-359, 2009.  •  Kandel ER, Schwartz JH, Jessell TM, Siegelbaum SA, Hudspeth AJ. Principles of Neural Science, 5th Edition. New York:  McGraw-Hill, 2013.  •  Kandel ER, Schwartz JH, Jessell TM. Principles of Neural Science, 4th edition. New York: McGraw-Hill Companies, 2000.  •  Kennedy PM, Cresswell AG, Chua R, Inglis JT. Vestibulospinal influences on lower limb motoneurons. Can J Physiol  Pharmacol 82: 675-681, 2004.  •  Koeppen BM, Stanton BA. Berne & Levy Physiology, 6th edition. Philadelphia, PA: Mosby, Elsevier, 2010.  •  Kolb B, Whishaw IQ. An introduction to brain and behavior. New York: Worth Publishers, 2001.  •  Land MF. Eye movements and the control of actions in everyday life. Prog Retinal Eye Res 25: 296-324, 2006.  •  Magill RA. Motor learning and control: concepts and applications. 8th Edition. Boston, MA: McGraw-Hill, 2007.  •  Marigold DS. Role of peripheral visual cues in online visual guidance of locomotion. Exerc Sport Sci Revs 36: 145-151,  2008.  •  OpenStax: https://openstax.org/details/books/anatomy-and-physiology; accessed June 2020.  •  Proske U, Gandevia SC. The proprioceptive senses: their roles in signaling body shape, body position and movement,  and muscle force. Physiological Reviews 92: 1651-1697, 2012.  •  Purves D, Augustine GJ, Fitzpatrick D, Hall WC, LaMantia A-S, McNamara JO, Williams SM. Neuroscience, 3rd edition.  Sinauer Associates, Inc., 2004.  •  Rothwell JC, Traub MM, Day BL, Obeso JA, Thomas PK, Marsden CD. Manual motor performance in a deafferented  man. Brain 105: 515-542, 1982  •  Schmidt RA, Lee TD. Motor Control and Learning: A Behavioral Emphasis. 4th Edition. Champaign, Ill: Human Kinetics  Publishers, 2005.   •  Shumway-Cook A, Woollacott MH. Motor control: translating research into clinical practice. 3rd Edition. Philadelphia,  PA: Lippincott Williams & Wilkins, 2007.  •  Strzalkowksi NDJ, Peters RM, Inglis JT, Bent LR. Cutaneous afferent innervation of the human foot sole: what can we  learn from single-unit recordings? J Neurophysiol 120: 1233-1246, 2018.  •  Stanfield CL, Germann WJ. Principles of Human Physiology, 3rd edition. 2008.  •  Tresilian J. Sensorimotor control and learning. An Introduction to the Behavioral Neuroscience of Action. Palgrave  Macmillan, 2012.
****All figures are used in accordance with Copyright Act and SFU Copyright guidelines****