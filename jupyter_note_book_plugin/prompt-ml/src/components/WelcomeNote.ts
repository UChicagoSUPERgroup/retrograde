import { PopupNotification } from "./PopupNotification";

export class WelcomeNote extends PopupNotification {
  ////////////////////////////////////////////////////////////
  // Constructor
  ////////////////////////////////////////////////////////////

  constructor() {
    super("welcome", false, "Welcome", [{}]);
    this.addHeader("Welcome to PromptML");
        this.addParagraph(`Throughout the course of this data task, the PromptML plugin will provide information about the data and your decisions with respect to fairness. 
        The plugin provides information through distinct notifications that each provide different data and analysis. 
        This <span class="code-snippet-inline">Welcome Notification</span> provides background information about the plugin, other notifications, and the task itself.`);
    this.addSubheader("The Plugin Interface")
        this.addParagraph(`The plugin has two main interfaces, the side panel on the right that shows which notifications are available and the main window that provides the actual notification content. 
        You can open, close, and dismiss notifications as needed, but please note that the information changes as cells are executed`);
    this.addSubheader("Protected Data")
        this.addParagraph(`Many of the notifications include references to so-called protected data. 
        A protected class is group of people sharing a common trait who are legally 
        protected from being discriminated against on the basis of that trait. 
        Some common examples include race, gender, and pregnancy status.`);
        this.addRawHtmlElement(document.createElement("br"));
        this.addParagraph(`The plugin attempts to identify protected data for the dataframes within this data task. 
        You are able to modify these classifications within the <span class="code-snippet-inline">Protected Columns</span> notification, as the plugin
        may falsely mark or fail to mark a given column as protected. The changes made within this notification will affect how other notifications analyze aspects of fairness.`)
  }

  ////////////////////////////////////////////////////////////
  // Abstractions
  // Tries to make note generation more intuitive and consistent across
  // different note types and styles.
  ////////////////////////////////////////////////////////////

  public _populateNote(): HTMLDivElement {
    var elem = document.createElement("div");
    elem.classList.add("promptMl");
    elem.style.cssText = "padding: 15px; overflow: scroll;";
    return elem;
  }

  export(): HTMLDivElement {
    return this._content; // doesn't clone, returns the actual element -- prevents the event listeners from being removed
  }
}
