"""Contenu HTML des manuels utilisateur (FR / EN / ES / IT)."""

SHORTCUTS = [("Ctrl+O", "act_open"), ("Ctrl+R", "act_reselect_sim"), ("Ctrl+S", "act_save_xml"),
             ("Ctrl+L", "act_load_xml"), ("Ctrl+E", "act_export_pdf"),
             ("Ctrl+Shift+P", "act_preview"), ("Ctrl+P", "act_print"), ("F1", "act_manual")]

MANUALS = {
"fr": """
<h1>FlightCard Generator — Manuel utilisateur</h1>
<p>FlightCard Generator crée, prévisualise et imprime la <b>carte de vol</b> exigée sur les
champs de tir (format Rocketry France / Tripoli) à partir d'une simulation OpenRocket
(<code>.ork</code>) ou RockSim (<code>.rkt</code>).</p>

<h2>1. Installation et démarrage</h2>
<ol><li>Installez Python 3.10 ou plus récent.</li>
<li>Dans le dossier du projet : <code>pip install -r requirements.txt</code></li>
<li>Lancez : <code>python main.py</code> (ou <code>python main.py ma_fusee.ork</code>).</li></ol>
<p>L'application fonctionne à l'identique sous Windows, macOS et Linux.</p>

<h2>2. Importer une simulation</h2>
<ul><li>Glissez-déposez un fichier <code>.ork</code>, <code>.rkt</code> ou une fiche <code>.xml</code>
dans la zone en pointillés (ou n'importe où dans la fenêtre), ou utilisez
<b>Fichier › Ouvrir une simulation</b>.</li>
<li>Si le fichier contient plusieurs simulations, une fenêtre liste chacune (moteurs, apogée,
vitesse max, état) : choisissez celle à utiliser. <b>Fichier › Choisir une autre simulation</b>
permet de changer ensuite sans rouvrir le fichier.</li>
<li>Sont extraits : nom, longueur, diamètre, masse au décollage, CG, CP, marge statique,
moteurs par étage et cluster, impulsion, systèmes de récupération, conditions de lancement,
résultats (apogée, vitesses, accélération, Mach, temps, retard optimal), événements de vol
et avertissements.</li></ul>
<p><b>OpenRocket :</b> la masse, le CG et le CP proviennent des données de vol enregistrées.
Si elles sont absentes, enregistrez la fusée dans OpenRocket avec l'option
« Enregistrer toutes les données simulées », ou saisissez ces valeurs à la main.</p>
<p><b>RockSim :</b> le format n'est pas documenté publiquement ; la lecture est tolérante et
toute valeur peut être corrigée.</p>

<h2>3. Profil pilote, lieu et logo</h2>
<ul><li>Onglet <b>Pilote et vol</b> : nom, prénom, n° de licence, niveau de certification Tripoli.
Le profil est mémorisé (bouton <b>Mémoriser le profil</b> et automatiquement à la fermeture).</li>
<li>Le <b>lieu de lancement</b> est une liste déroulante éditable : chaque lieu utilisé est ajouté
à l'historique. « Oublier ce lieu » le retire.</li>
<li><b>Logo de l'association</b> (PNG/JPG) : il est copié dans le dossier de données et
apparaît en haut à gauche de la fiche.</li></ul>

<h2>4. Modifier la fiche</h2>
<p>Tous les champs pré-remplis restent modifiables. Certains champs sont <b>automatiques</b> :
impulsion totale, niveau du vol (Level), poussée moyenne au décollage, rapport poussée/poids et
marge statique. Ils se recalculent lorsque leurs données sources changent, tant que vous ne les
avez pas modifiés vous-même. Le bouton <b>Recalculer les valeurs automatiques</b> force le
recalcul.</p>
<p>Rapport poussée/poids = poussée moyenne (N) / (masse (kg) × 9,81) :
≥ 5 vol validé ; entre 3 et 5 soumis à l'approbation du RSO ; &lt; 3 vol interdit.
Pour un cluster, saisissez par exemple « 2 × H128W » dans la ligne Cluster.</p>

<h2>5. Langues</h2>
<p>La langue de l'interface est détectée au premier démarrage et se change à chaud dans la barre
d'outils. La <b>langue d'impression</b> se choisit séparément : on peut travailler en français et
imprimer la fiche en anglais.</p>

<h2>6. Sauvegarder, imprimer, exporter</h2>
<ul><li><b>Sauvegarder la fiche (XML)</b> enregistre tous les champs, la courbe de vol et le logo ;
<b>Charger une fiche (XML)</b> la restaure.</li>
<li><b>Aperçu avant impression</b>, <b>Imprimer</b> et <b>Exporter en PDF</b> produisent une page A4
paysage reproduisant la carte de vol, et en option une annexe détaillée (caractéristiques,
propulsion, conditions, résultats, événements, avertissements, graphique altitude / vitesse).</li>
<li>Les parties LCO et RSO sont laissées vierges pour être remplies sur le terrain.</li></ul>

<h2>7. Données enregistrées</h2>
<p>Le fichier <code>settings.json</code> et le logo sont stockés dans le dossier de données de
l'utilisateur : <code>%APPDATA%\\FlightCard\\FlightCard Generator</code> (Windows),
<code>~/Library/Application Support/FlightCard/FlightCard Generator</code> (macOS),
<code>~/.local/share/FlightCard/FlightCard Generator</code> (Linux).</p>

<h2>8. Raccourcis clavier</h2>
{shortcuts}
<p><i>Le pilote reste seul responsable des valeurs portées sur la fiche : vérifiez-les toujours
avant de la présenter au RSO.</i></p>
""",

"en": """
<h1>FlightCard Generator — User manual</h1>
<p>FlightCard Generator creates, previews and prints the <b>flight card</b> required at launch
sites (Rocketry France / Tripoli layout) from an OpenRocket (<code>.ork</code>) or RockSim
(<code>.rkt</code>) simulation.</p>

<h2>1. Installation and start-up</h2>
<ol><li>Install Python 3.10 or newer.</li>
<li>In the project folder: <code>pip install -r requirements.txt</code></li>
<li>Run: <code>python main.py</code> (or <code>python main.py my_rocket.ork</code>).</li></ol>
<p>The application behaves the same on Windows, macOS and Linux.</p>

<h2>2. Importing a simulation</h2>
<ul><li>Drag and drop an <code>.ork</code>, <code>.rkt</code> or <code>.xml</code> card file onto the
dashed area (or anywhere in the window), or use <b>File › Open simulation</b>.</li>
<li>If the file holds several simulations, a dialog lists them (motors, apogee, max velocity,
status): pick the one to use. <b>File › Choose another simulation</b> switches later without
reopening the file.</li>
<li>Extracted data: name, length, diameter, lift-off mass, CG, CP, static margin, motors per
stage and cluster, impulse, recovery devices, launch conditions, results (apogee, velocities,
acceleration, Mach, times, optimum delay), flight events and warnings.</li></ul>
<p><b>OpenRocket:</b> mass, CG and CP come from the stored flight data. If it is missing, save the
rocket in OpenRocket with the “save all simulated data” option, or type the values by hand.</p>
<p><b>RockSim:</b> the format is not publicly documented; reading is tolerant and every value can be
corrected.</p>

<h2>3. Pilot profile, place and logo</h2>
<ul><li><b>Pilot &amp; flight</b> tab: last name, first name, license number, Tripoli certification
level. The profile is saved (<b>Save profile</b> button, and automatically on exit).</li>
<li>The <b>launch site</b> is an editable drop-down list: every place used is added to the history.
“Forget this place” removes it.</li>
<li><b>Club logo</b> (PNG/JPG): copied into the data folder and shown in the top-left corner of the
card.</li></ul>

<h2>4. Editing the card</h2>
<p>All pre-filled fields stay editable. Some fields are <b>automatic</b>: total impulse, flight
level, average lift-off thrust, thrust-to-weight ratio and static margin. They are recomputed
when their source data changes, as long as you have not edited them yourself. The
<b>Recalculate automatic values</b> button forces a recalculation.</p>
<p>Thrust-to-weight = average thrust (N) / (mass (kg) × 9.81): ≥ 5 approved; 3 to 5 subject to RSO
approval; &lt; 3 forbidden. For a cluster, type e.g. “2 × H128W” in the Cluster row.</p>

<h2>5. Languages</h2>
<p>The interface language is detected on first start and can be changed on the fly from the
toolbar. The <b>print language</b> is chosen separately: you can work in English and print the
card in French.</p>

<h2>6. Saving, printing, exporting</h2>
<ul><li><b>Save card (XML)</b> stores every field, the flight curve and the logo; <b>Load card (XML)</b>
restores it.</li>
<li><b>Print preview</b>, <b>Print</b> and <b>Export to PDF</b> produce an A4 landscape page that
reproduces the flight card, plus an optional detailed appendix (characteristics, propulsion,
conditions, results, events, warnings, altitude/velocity chart).</li>
<li>The LCO and RSO sections are left blank to be filled in on the field.</li></ul>

<h2>7. Stored data</h2>
<p><code>settings.json</code> and the logo live in the user data folder:
<code>%APPDATA%\\FlightCard\\FlightCard Generator</code> (Windows),
<code>~/Library/Application Support/FlightCard/FlightCard Generator</code> (macOS),
<code>~/.local/share/FlightCard/FlightCard Generator</code> (Linux).</p>

<h2>8. Keyboard shortcuts</h2>
{shortcuts}
<p><i>The pilot alone is responsible for the values on the card: always check them before
presenting it to the RSO.</i></p>
""",

"es": """
<h1>FlightCard Generator — Manual de usuario</h1>
<p>FlightCard Generator crea, previsualiza e imprime la <b>ficha de vuelo</b> exigida en los
campos de lanzamiento (formato Rocketry France / Tripoli) a partir de una simulación OpenRocket
(<code>.ork</code>) o RockSim (<code>.rkt</code>).</p>

<h2>1. Instalación e inicio</h2>
<ol><li>Instale Python 3.10 o posterior.</li>
<li>En la carpeta del proyecto: <code>pip install -r requirements.txt</code></li>
<li>Ejecute: <code>python main.py</code> (o <code>python main.py mi_cohete.ork</code>).</li></ol>
<p>La aplicación funciona igual en Windows, macOS y Linux.</p>

<h2>2. Importar una simulación</h2>
<ul><li>Arrastre un archivo <code>.ork</code>, <code>.rkt</code> o una ficha <code>.xml</code> a la zona
punteada (o a cualquier parte de la ventana), o use <b>Archivo › Abrir simulación</b>.</li>
<li>Si el archivo contiene varias simulaciones, una ventana las enumera (motores, apogeo,
velocidad máxima, estado): elija la que desea. <b>Archivo › Elegir otra simulación</b> permite
cambiar después sin volver a abrir el archivo.</li>
<li>Datos extraídos: nombre, longitud, diámetro, masa al despegue, CG, CP, margen estático,
motores por etapa y clúster, impulso, sistemas de recuperación, condiciones de lanzamiento,
resultados (apogeo, velocidades, aceleración, Mach, tiempos, retardo óptimo), eventos de vuelo
y advertencias.</li></ul>
<p><b>OpenRocket:</b> la masa, el CG y el CP proceden de los datos de vuelo guardados. Si faltan,
guarde el cohete en OpenRocket con la opción «guardar todos los datos simulados» o introduzca
los valores a mano.</p>
<p><b>RockSim:</b> el formato no está documentado públicamente; la lectura es tolerante y cualquier
valor puede corregirse.</p>

<h2>3. Perfil del piloto, lugar y logotipo</h2>
<ul><li>Pestaña <b>Piloto y vuelo</b>: apellido, nombre, n.º de licencia y nivel de certificación
Tripoli. El perfil se guarda (botón <b>Guardar perfil</b> y automáticamente al salir).</li>
<li>El <b>lugar de lanzamiento</b> es una lista desplegable editable: cada lugar utilizado se añade
al historial. «Olvidar este lugar» lo elimina.</li>
<li><b>Logotipo del club</b> (PNG/JPG): se copia en la carpeta de datos y aparece arriba a la
izquierda de la ficha.</li></ul>

<h2>4. Editar la ficha</h2>
<p>Todos los campos rellenados siguen siendo editables. Algunos son <b>automáticos</b>: impulso
total, nivel del vuelo, empuje medio al despegue, relación empuje/peso y margen estático. Se
recalculan cuando cambian sus datos de origen, mientras no los haya modificado usted. El botón
<b>Recalcular los valores automáticos</b> fuerza el recálculo.</p>
<p>Relación empuje/peso = empuje medio (N) / (masa (kg) × 9,81): ≥ 5 vuelo validado; de 3 a 5
sujeto a la aprobación del RSO; &lt; 3 prohibido. Para un clúster, escriba por ejemplo
«2 × H128W» en la fila Clúster.</p>

<h2>5. Idiomas</h2>
<p>El idioma de la interfaz se detecta en el primer inicio y se cambia en caliente desde la
barra de herramientas. El <b>idioma de impresión</b> se elige por separado.</p>

<h2>6. Guardar, imprimir, exportar</h2>
<ul><li><b>Guardar ficha (XML)</b> almacena todos los campos, la curva de vuelo y el logotipo;
<b>Cargar ficha (XML)</b> la restaura.</li>
<li><b>Vista previa</b>, <b>Imprimir</b> y <b>Exportar a PDF</b> generan una página A4 apaisada que
reproduce la ficha de vuelo, con un anexo detallado opcional.</li>
<li>Las secciones LCO y RSO quedan en blanco para rellenarlas en el campo.</li></ul>

<h2>7. Datos guardados</h2>
<p><code>settings.json</code> y el logotipo se guardan en la carpeta de datos del usuario:
<code>%APPDATA%\\FlightCard\\FlightCard Generator</code> (Windows),
<code>~/Library/Application Support/FlightCard/FlightCard Generator</code> (macOS),
<code>~/.local/share/FlightCard/FlightCard Generator</code> (Linux).</p>

<h2>8. Atajos de teclado</h2>
{shortcuts}
<p><i>El piloto es el único responsable de los valores de la ficha: compruébelos siempre antes de
presentarla al RSO.</i></p>
""",

"it": """
<h1>FlightCard Generator — Manuale utente</h1>
<p>FlightCard Generator crea, visualizza in anteprima e stampa la <b>scheda di volo</b> richiesta
sui campi di lancio (formato Rocketry France / Tripoli) a partire da una simulazione OpenRocket
(<code>.ork</code>) o RockSim (<code>.rkt</code>).</p>

<h2>1. Installazione e avvio</h2>
<ol><li>Installare Python 3.10 o successivo.</li>
<li>Nella cartella del progetto: <code>pip install -r requirements.txt</code></li>
<li>Avviare: <code>python main.py</code> (oppure <code>python main.py mio_razzo.ork</code>).</li></ol>
<p>L'applicazione funziona allo stesso modo su Windows, macOS e Linux.</p>

<h2>2. Importare una simulazione</h2>
<ul><li>Trascinare un file <code>.ork</code>, <code>.rkt</code> o una scheda <code>.xml</code> nella zona
tratteggiata (o in qualsiasi punto della finestra), oppure usare <b>File › Apri simulazione</b>.</li>
<li>Se il file contiene più simulazioni, una finestra le elenca (motori, apogeo, velocità
massima, stato): scegliere quella da usare. <b>File › Scegli un'altra simulazione</b> consente di
cambiarla senza riaprire il file.</li>
<li>Dati estratti: nome, lunghezza, diametro, massa al decollo, CG, CP, margine statico, motori
per stadio e cluster, impulso, sistemi di recupero, condizioni di lancio, risultati (apogeo,
velocità, accelerazione, Mach, tempi, ritardo ottimale), eventi di volo e avvisi.</li></ul>
<p><b>OpenRocket:</b> massa, CG e CP provengono dai dati di volo salvati. Se mancano, salvare il
razzo in OpenRocket con l'opzione «salva tutti i dati simulati» o inserire i valori a mano.</p>
<p><b>RockSim:</b> il formato non è documentato pubblicamente; la lettura è tollerante e ogni
valore può essere corretto.</p>

<h2>3. Profilo pilota, luogo e logo</h2>
<ul><li>Scheda <b>Pilota e volo</b>: cognome, nome, n. di licenza, livello di certificazione
Tripoli. Il profilo viene memorizzato (pulsante <b>Salva profilo</b> e automaticamente in
chiusura).</li>
<li>Il <b>luogo di lancio</b> è un elenco a discesa modificabile: ogni luogo usato viene aggiunto
alla cronologia. «Dimentica questo luogo» lo rimuove.</li>
<li><b>Logo dell'associazione</b> (PNG/JPG): viene copiato nella cartella dei dati e compare in
alto a sinistra della scheda.</li></ul>

<h2>4. Modificare la scheda</h2>
<p>Tutti i campi precompilati restano modificabili. Alcuni campi sono <b>automatici</b>: impulso
totale, livello del volo, spinta media al decollo, rapporto spinta/peso e margine statico.
Vengono ricalcolati quando cambiano i dati di origine, finché non li si modifica a mano. Il
pulsante <b>Ricalcola i valori automatici</b> forza il ricalcolo.</p>
<p>Rapporto spinta/peso = spinta media (N) / (massa (kg) × 9,81): ≥ 5 volo approvato; da 3 a 5
soggetto all'approvazione del RSO; &lt; 3 vietato. Per un cluster, scrivere ad esempio
«2 × H128W» nella riga Cluster.</p>

<h2>5. Lingue</h2>
<p>La lingua dell'interfaccia è rilevata al primo avvio e si cambia al volo dalla barra degli
strumenti. La <b>lingua di stampa</b> si sceglie separatamente.</p>

<h2>6. Salvare, stampare, esportare</h2>
<ul><li><b>Salva scheda (XML)</b> memorizza tutti i campi, la curva di volo e il logo;
<b>Carica scheda (XML)</b> la ripristina.</li>
<li><b>Anteprima di stampa</b>, <b>Stampa</b> ed <b>Esporta in PDF</b> producono una pagina A4
orizzontale che riproduce la scheda di volo, con un allegato dettagliato opzionale.</li>
<li>Le sezioni LCO e RSO restano vuote per essere compilate sul campo.</li></ul>

<h2>7. Dati memorizzati</h2>
<p><code>settings.json</code> e il logo si trovano nella cartella dati dell'utente:
<code>%APPDATA%\\FlightCard\\FlightCard Generator</code> (Windows),
<code>~/Library/Application Support/FlightCard/FlightCard Generator</code> (macOS),
<code>~/.local/share/FlightCard/FlightCard Generator</code> (Linux).</p>

<h2>8. Scorciatoie da tastiera</h2>
{shortcuts}
<p><i>Il pilota è l'unico responsabile dei valori riportati sulla scheda: verificarli sempre prima
di presentarla al RSO.</i></p>
""",
}
