# SimDB technical design

## Introduction

This document summarises the design of the IMAS simulation management system
(SimDB) as is organised as follows:
* Supported platforms
* High level description of the system and API design
* Overview of the CLI functionality
* Design of the metadata elements
* Outline of simulation data validation

## Supported Platforms

The following platforms are support for SimDB: Linux, macOS, Windows.

## High level description

The system will have two major components: one local to the user, and the other
remote.

The local component will be provided as a Command Line Interface (CLI) tool,
similar to tools such as git or openssl.

```bash
script <command> <command specific options and passed parameters>
```

The commands will be divided into a hierarchical tree of commands, with each
level of commands having their own help available, i.e.:

```bash
script <command> --help
script <command> <sub_command> --help
```

The remote component will manage the reference database and associated
metadata. Interactions between the two components will be through a REST API,
using SSL encrypted HTTP (HTTPS).

### Architecture overview

The following images shows the high-level components of the system.

![simdb architecture](simdb-architecture.svg)

A description of the components is as follows:

1. The CLI tool: Used to manage the simulation metadata, file manifest and
provenance and to allow the user to query these elements.
2. The SQLite DBMS: To store the user ingested simulations before they have
been pushed to the remote system.
3. The Simulation Directory: The directory where the simulation has been
run and where the simulation files will be retrieved from when they are
pushed to the remote system.
4. The Remote REST API: The remote API which processes requests from
the user CLI to receive pushed simulations and store them ready for
validation and publishing.
5. The Staging Directory: The location the pushed simulation files are
transferred to while waiting for validation.
6. The Remote DBMS: The DBMS where the simulation metadata and
provenance will be saved for all uploaded simulation along with their
validation status flags.
   
### Assumptions

1. Interactions between the CLI and the Remote central database
    1. Are Stateless
    2. May not use a permanent network connection
    3. Will be based on a Simulation Identifier (a UUID)
    4. Will utilise a temporary directory for all exchanged objects
        1. Use a directory named as the UUID
        2. Moved on simulation COMMIT to a permanent directory
    5. Authentication and authorisation will be needed for each interaction on the remote database
2. The Provenance database may use a different DBMS
    1. DAG based schema
        1. Triple is two nodes, and a connected edge
    2. The schema can be written as standard SQL statements
    
## CLI functionality

The following functionality will be provided by the CLI tool.

### Database Query
1. Query the user’s local database
    1. CLI text input with context
2. Query the remote central database
    1. CLI text input with context
3. Query Output
    1. Text written to command line formatted as YAML
    2. User command line redirection to output file
   
### Request a Simulation UUID
1. CLI request with context
    1. context=[alias]
2. Output written to command line

### File Manifest
1. Simulation Data Files
    1. Simulation Plan, Input files, Output files
    2. Location
    3. Class (Plan, Input, Output, Metadata, Provenance, …)
    4. Hash checksum
2. Data Import
    1. Set of Simulation Data Files
    2. Metadata file
    3. Provenance file
3. Data Export
    1. Set of Simulation Data Files
    2. Metadata file
    3. Provenance file
    
### Data Import/Export
1. A JSON transport object containing all simulation data including
simulation plan, metadata, provenance, etc.
2. Binary IO streams sent via HTTP for each simulation file
    1. Input files
    2. Output files
    3. IMAS API log file
    4. UDA log file

### Log Files
1. IMAS API Log
    1. Ordered list of all IMAS low level API calls
2. UDA Data Access Log
    1. Ordered list of all UDA data access and ingest calls

### Metadata
1. Metadata file
    1. Name value pairs compliant with Dublin Core
        1. YAML format
        2. Ingested into the CLI SQLite DBMS
    2. Exchanged between local and remote system as part of the JSON
transport object
2. Provenance SQLite database file
    1. Preferably W3C PROV (RDF) triples, otherwise name value pairs
        1. Collected by future provenance instrumentation within
        IMAS and written to a user SQLite database
    2. Ingested by the CLI SQLite DBMS

### File Formats
1. Manifest
    * YAML Ascii file
2. Metadata
    * Name value pairs
    * YAML Ascii file
    * One pair per record
3. Provenance
    * YAML Ascii file
4. Simulation Plan
    * Microsoft Word or Adobe PDF
5. Simulation Input
    * Ascii
    * Binary: IDS
6. Simulation Output
    * Binary: IDS
7. Configuration file
    * Ascii
    * Name value pairs
8. Git diff and status file
    * Ascii
9. IMAS API Log
    * CSV Ascii
10. UDA Log
    * CSV Ascii
11. IMAS Open/Create arguments
    * Name value pairs
    
## Use case narratives and system processing actions

### Prepare for a new simulation

### Execute the simulation

### Register the simulation locally using the imasdb CLI

### Deposit the simulation remotely using the imasdb CLI

## Contents of the metadata file proforma

The proforma file contains the value descriptions. Text lines beginning # are
ignored. Names without values are not ingested.

| Name | Value description |
| ---- | ----------------- |
| Title | The name given to the resource.<br /><br /> Typically, a Title will be a name by which the resource is formally known.<br /><br /> The title element may be repeated multiple times to include variants of the title. |
| Subject | The topic of the content of the resource.<br /><br /> Typically, a Subject will be expressed as keywords or key phrases or classification codes that describe the topic of the resource. Recommended best practice is to select a value from a controlled vocabulary or formal classification scheme.<br /><br /> Select subject keywords from the Title or Description information, or from within a text resource.<br /><br /> Choose the most significant and unique words for keywords.<br /><br /> If multiple vocabulary terms or keywords are used, use separate iterations of the Subject element. |
| Description | An account of the content of the resource.<br /><br /> Description may include but is not limited to: an abstract, table of contents, reference to a graphical representation of content or a free-text account of the content. |
| Type | The nature or genre of the content of the resource.<br /><br /> Recommended best practice is to select a value from a controlled vocabulary. To describe the physical or digital manifestation of the resource, use the FORMAT element.<br /><br /> If the resource is composed of multiple mixed types then multiple or repeated Type elements should be used to describe the main components. |
| Source | A Reference to a resource from which the present resource is derived - in whole or part.<br /><br /> Recommended best practice is to reference the resource by means of a formal identification system. |
| Relation | A reference to a related resource.<br /><br /> Recommended best practice is to reference the resource by means of a formal identification system. |
| Coverage | The extent or scope of the content of the resource.<br /><br /> Coverage will typically include spatial location, temporal period, or jurisdiction (such as a named entity).<br /><br /> Recommended best practice is to select a value from a controlled vocabulary. Where appropriate, named  places or time periods should be used in preference to  numeric identifiers such as sets of co-ordinates or date  ranges.  Repeat for each class of coverage. |
| Creator | An entity primarily responsible for making the content of the resource.<br /><br /> Multiple creators should be listed separately. |
| Publisher | The entity responsible for making the resource available.<br /><br /> The intent of specifying this field is to identify the entity  that provides access to the resource. If the Creator and  Publisher are the same, do not repeat the name in the Publisher area. If the nature of the responsibility is ambiguous, the recommended practice is to use Publisher for organizations, and Creator for individuals. In cases of ambiguous responsibility, use Contributor. |
| Contributor | An entity (name) responsible for making contributions to the content of the resource. Examples of a Contributor include a person, an organization or a service. |
| Rights | Information about rights held in and over the resource. If the rights element is absent, no assumptions can be made about rights with respect to the resource. |
| Date | A date associated with an event in the life cycle of the resource. Typically, Date will be associated with the creation or availability of the resource. Recommended best practice for encoding the date value is defined in ISO 8601 and follows the YYYY-MM-DD format.<br /><br /> If the full date is unknown, month and year (YYYY-MM) or just year (YYYY) may be used. |
| Format | The physical or digital manifestation of the resource. Typically, Format may include the media-type.<br /><br /> Recommended best practice is to select a value from a controlled vocabulary.<br /><br /> Repeat for each class of category. |
| Identifier | An unambiguous reference to the resource within a given context.<br /><br /> Recommended best practice is to identify the resource by means of a string or number conforming to a formal identification system. Examples of formal identification systems include the Uniform Resource Identifier (URI) (including the Uniform Resource Locator (URL), the Digital Object Identifier (DOI) and the International Standard Book Number (ISBN).<br /><br /> This element can also be used for local identifiers (e.g. ID numbers) assigned by the Creator of the resource to apply to a particular item. It should not be used for identification of the metadata record itself. |
| Language | A language of the intellectual content of the resource.<br /><br /> Recommended best practice for the values of the Language element is defined by RFC 3066 which, in conjunction with ISO 639, defines two- and three-letter primary language tags with optional sub-tags. Examples include "en" or "eng" for English, "akk" for Akkadian, and "en-GB" for English used in the United Kingdom. |
| Audience | A class of entity for whom the resource is intended or useful. A class of entity may be determined by the creator or the publisher or by a third party.<br /><br /> Audience terms are best utilized in the context of formal or informal controlled vocabularies.<br /><br />Element of Qualified Dublin Core |
| Provenance | A statement of any changes in ownership and custody of the resource since its creation that are significant for its authenticity, integrity and interpretation. The statement may include a description of any changes successive custodians made to the resource.<br /><br />Element of Qualified Dublin Core |
| RightsHolder | A person or organization owning or managing rights over the resource. Recommended best practice is to use the URI or name of the Rights Holder to indicate the entity.<br /><br /> Element of Qualified Dublin Core |
| InstructionalMethod | A process, used to engender knowledge, attitudes and skills, that the resource is designed to support. Instructional Method will typically include ways of presenting instructional materials or conducting instructional activities, patterns of learner-to-learner and learner-to-instructor interactions, and mechanisms by which group and individual levels of learning are measured. Instructional methods include all aspects of the instruction and learning processes from planning and implementation through evaluation and feedback.<br /><br /> Best practice is to use terms from controlled vocabularies, whether developed for the use of a particular project or in general use in an educational context. |
| AccrualMethod | The method by which items are added to a collection. Recommended best practice is to use a value from a  controlled vocabulary. |
| AccrualPeriodicity | The frequency with which items are added to a collection. Recommended best practice is to use a value from a controlled vocabulary.
| AccrualPolicy | The policy governing the addition of items to a collection. Recommended best practice is to use a value from a controlled vocabulary.

### DC element qualifiers

Qualifier elements are terms that extend or refine the original Dublin Core Metadata Element Set. They are associated with an original element.

There are two broad classes of qualifiers:
1. **Element Refinement** - make the meaning of an element narrower or more specific.
2. **Encoding Scheme** - these qualifiers identify schemes that aid in the interpretation of an element value. These schemes include controlled  vocabularies and formal notations or parsing rules. A value expressed using an encoding scheme will thus be a token selected from a controlled vocabulary, or a string formatted in accordance with a formal notation.

| DC Element | Element Refinement Qualifier | Element Encoding Scheme |
| --- | --- | --- |
| Title | *Alternative*<br /><br /> Any form of the title used as a substitute or alternative to the formal title of the resource.| |
| Creator | | |
| Subject | | |
| Description | *Abstract*<br />*tableOfContents*<br /><br />A summary of the contents of the resource.<br /><br />A list of subunits of the content of the resource. | |
| Publisher | | |
| Contributor | | |
| Date | Created<br />Valid<br />Available<br />Issued<br />Modified<br />DateAccepted<br />DateCopyrighted<br />DateSubmitted | DCMI Period<br />W3C-DTF |
| Type | | |
| Format | Extent<br />Medium | |
| Identifier | BibliographicCitation | |
| Source | | |
| Language | | ISO 639-2RFC 3066 |
| Relation | Is Version Of<br />Has Version<br />Is Replaced By<br />Replaces<br />Is Required By<br />Requires<br />Is Part Of<br />Has Part<br />Is Referenced By<br />References<br />Is Format Of<br />Has Format<br />Conforms To | |
| Coverage | Spatial<br />Temporal | DCMI Period<br />W3C-DTF |
| Rights | AccessRights<br />Licence | |
| Audience | Mediator<br />EducationLevel | |
| Provenance | | |
| RightsHolder | | |
| InstructionalMethod | | |
| AccrualMethod | | |
| AccrualPeriodicity | | |

## Simulation Validation Testing

Testing cannot verify the accuracy of simulation results. It can however test that data complies with certain expectations: value range, value distribution, and  value deviation from standard reference data. The results of testing can become  a resource to be utilised in locating simulation data: the results become classifiers that are recorded in a relational database that may be queried by  users and applications.

If an IDS has been populated with data, there are several data quantities that must be assigned values: the ids_properties and code structures. Additionally, if ids_properties/homogeneous_time is set to the value 1, the array time must be  filled with values other than the missing value.

Data that originates from pre-existing IDS files and are used as inputs to the workflow model needs not be tested as they are not the results of the workflow. However, these need to be identified (whole IDS objects and specific individual IDS data entities) to the validation testing routines, so they can be skipped over. It is simpler to identify only the specific IDS objects that need be tested.

### Initialisation

To help assist in the generation of test comparison data, the application will have a start-up mode where the tests are not run; instead the statistics data are recorded. These can then be utilised to form the initial set of test comparison data.

Start-up data may be written to a temporary SQL database table for analysis and aggregation. From this an appropriate set of comparison statistics may be generated.

Additional test parameters that will need to be set are the check on missing values, and the check on mandatory data fields.

| # | Test | Description |
| --- | --- | --- |
| 1 | Verify all data are within expected limits. | 1. Compare statistics drawn from the data against a standard set: Mean, Max, Min, Standard Deviation.<br />2. Verify there are no missing data within the set of data.<br />3. Verify data has been written – the data entity is a mandatory entity so must be populated with non-missing data.<br /><br /> The set of test values are identified within an  SQL database using 3 classifiers: device name,  experiment or simulation scenario, and the data entity name.<br /><br /> Data entity names that include hierarchical branching index values (structure arrays) may be classed using a wild card character, ‘*’, to signify any index value. These set of test values are to be used with all similar data entities. |
| 2 | Compare all data with reference data. The reference data may be data for a different occurrence number contained in the same data file. | All data entities within the IDSs to be validated are compared with the same IDS data entities from a reference dataset.<br /><br /> 1. Difference in standard statistics: Mean, Max, Min, Standard Deviation, and number of elements.<br /> 2. If the coordinate data are known, the integral between curves (for the common coordinate range) as a percentage of the integral of the data to be tested.<br /><br /> As with test #1, expected test values are identified by querying a SQL database. |
